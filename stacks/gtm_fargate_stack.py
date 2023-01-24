import os
from aws_cdk import (
    Stack,
    aws_certificatemanager as certificatemanager,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_route53 as route53,
)
from constructs import Construct
from utils.fargate_resource_validator import validate_fargate_resources


class ServerSideGTMFargateStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cpu = self.node.try_get_context('cpu') or 256
        mem = self.node.try_get_context('mem') or 512
        desired_node_count = self.node.try_get_context('desiredNodeCount') or 1
        task_max_capacity = self.node.try_get_context('taskMaxCapacity') or 2
        task_min_capacity = self.node.try_get_context('taskMinCapacity') or 1
        target_cpu_utilization = self.node.try_get_context('targetCpuUtilization') or 80
        certificate_arn = self.node.try_get_context('certificateArn')
        domain = self.node.try_get_context('domain')
        
        # Validate cpu + mem
        validate_fargate_resources(cpu, mem)

        # Get Certificate
        certificate: certificatemanager.ICertificate = None
        if certificate_arn:
            certificate = certificatemanager.Certificate.from_certificate_arn(
                self, 'Certificate',
                certificate_arn=certificate_arn
            )

        # Get Domain's Hosted Zone
        hosted_zone: route53.IHostedZone = None
        if domain:
            hosted_zone = route53.HostedZone.from_lookup(
                self, 'HostedZone',
                domain_name=domain
            )

        # Create VPC
        vpc = ec2.Vpc(self, "vpc",
            cidr=ec2.Vpc.DEFAULT_CIDR_RANGE,
            max_azs=2,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            nat_gateways=2)

        # Create ECS Fargate Cluster
        cluster = ecs.Cluster(self, "FargateCluster", vpc=vpc)

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
            environment={
                "CONTAINER_CONFIG": os.environ['CONTAINER_CONFIG']
            }
        )

        # Create load balanced Fargate service
        fargate = ecs_patterns.ApplicationLoadBalancedFargateService(self, "Service",
            cluster=cluster,
            domain_name=domain,
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