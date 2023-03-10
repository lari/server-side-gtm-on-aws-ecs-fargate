from aws_cdk import (
    Stack,
    aws_certificatemanager as certificatemanager,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_route53 as route53,
)
from constructs import Construct
from utils.fargate_resource_validator import validate_fargate_resources


class ServerSideGTMFargateStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cpu = int(self.node.try_get_context('cpu')) or 256
        mem = int(self.node.try_get_context('mem')) or 512
        desired_node_count = int(self.node.try_get_context('desiredNodeCount')) or 1
        task_max_capacity = int(self.node.try_get_context('taskMaxCapacity')) or 2
        task_min_capacity = int(self.node.try_get_context('taskMinCapacity')) or 1
        target_cpu_utilization = int(self.node.try_get_context('targetCpuUtilization')) or 80
        container_config = self.node.try_get_context('containerConfig')
        certificate_arn = self.node.try_get_context('certificateArn')
        domain = self.node.try_get_context('domain')
        hosted_zone_id = self.node.try_get_context('hostedZoneId')
        hosted_zone_name = self.node.try_get_context('hostedZoneName')
        nat_gateways = int(self.node.try_get_context('natGateways')) | 2

        if not container_config:
            raise Exception("'containerConfig' context variable is required!")

        # Validate cpu + mem
        validate_fargate_resources(cpu, mem)

        # Check hosted zone
        hosted_zone: route53.IHostedZone = None
        if hosted_zone_id:
            hosted_zone = route53.HostedZone.from_hosted_zone_attributes(self, 'HostedZone',
                hosted_zone_id=hosted_zone_id,
                zone_name=hosted_zone_name
            )

        # Get Certificate
        certificate: certificatemanager.ICertificate = None
        if certificate_arn:
            certificate = certificatemanager.Certificate.from_certificate_arn(
                self, 'Certificate',
                certificate_arn=certificate_arn
            )
        elif hosted_zone:
            certificate = certificatemanager.Certificate(self, 'Certificate',
                domain_name=domain,
                validation=certificatemanager.CertificateValidation.from_dns(hosted_zone=hosted_zone)
            )

        # Create VPC
        vpc = ec2.Vpc(self, "vpc",
            cidr=ec2.Vpc.DEFAULT_CIDR_RANGE, # TODO: fix warning "Use ipAddresses instead"
            max_azs=2,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            nat_gateways=nat_gateways)

        # Create ECS Fargate Cluster
        cluster = ecs.Cluster(self, "FargateCluster", vpc=vpc)

        environment = {
            "CONTAINER_CONFIG": container_config
        }
        if domain and certificate:
            # Preview server requires HTTPS so we can create it only with custom domain and certificate.
            # It will use the same load balancer but different port.
            environment["PREVIEW_SERVER_URL"] = f"https://{domain}:444"

        # Create task definition with Docker container
        task_definition = ecs.FargateTaskDefinition(
            self, 'FargateTaskDefinition',
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.X86_64
            ),
            memory_limit_mib=mem,
            cpu=cpu,
        )
        task_definition.add_container(
            'Container',
            image=ecs.ContainerImage.from_asset('docker/'),
            readonly_root_filesystem=True,
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=construct_id
            ),
            port_mappings=[{
                "containerPort": 8080
            }],
            environment=environment
        )

        # Create load balanced Fargate service
        fargate = ecs_patterns.ApplicationLoadBalancedFargateService(self, "AlbService",
            cluster=cluster,
            # If there's no hosted zone, the domain will be a cname to aws issued domain
            domain_name=domain if hosted_zone else None,
            domain_zone=hosted_zone,
            certificate=certificate,
            listener_port=443 if certificate else 80,
            redirect_http=True if certificate else False,            
            cpu=cpu,
            desired_count=desired_node_count,
            memory_limit_mib=mem,
            task_definition=task_definition,
        )
        # Define health check
        fargate.target_group.configure_health_check(path='/healthz')

        # Set autoscaling parameters for the service
        fargate.service.auto_scale_task_count(
            max_capacity=task_max_capacity,
            min_capacity=task_min_capacity
        ).scale_on_cpu_utilization('cpu-utilization',
            target_utilization_percent=target_cpu_utilization
        )

        if domain and certificate:
            # Create task definition for preview server
            preview_task_definition = ecs.FargateTaskDefinition(
                self, 'FargateTaskDefinitionPreview',
                runtime_platform=ecs.RuntimePlatform(
                    operating_system_family=ecs.OperatingSystemFamily.LINUX,
                    cpu_architecture=ecs.CpuArchitecture.X86_64
                ),
                memory_limit_mib=mem,
                cpu=cpu,
            )
            preview_task_definition.add_container(
                'PreviewContainer',
                container_name='preview-container',
                image=ecs.ContainerImage.from_asset('docker/'),
                readonly_root_filesystem=True,
                logging=ecs.LogDriver.aws_logs(
                    stream_prefix=construct_id
                ),
                port_mappings=[{
                    "containerPort": 8080
                }],
                environment={
                    "CONTAINER_CONFIG": container_config,
                    'RUN_AS_PREVIEW_SERVER': 'true',
                }
            )

            # Create ECS Fargate service for preview server
            service = ecs.FargateService(self, "PreviewService",
                cluster=cluster,
                task_definition=preview_task_definition,
                desired_count=1
            )


            # Add PreviewService to the same load balaner with main service
            # Create listener to port 444 and target to preview service
            listener = fargate.load_balancer.add_listener(
                "PreviewListener",
                port=444,
                protocol=elbv2.ApplicationProtocol.HTTPS,
                certificates=[certificate]
            )
            preview_target_group = listener.add_targets("PreviewTarget",
                port=8080,
                targets=[service]
            )
            # Define health check
            preview_target_group.configure_health_check(path='/healthz')
