import aws_cdk as core
import aws_cdk.assertions as assertions

from stacks.gtm_fargate_stack import ServerSideGTMFargateStack

# example tests. To run these tests, uncomment this file along with the example
# resource in server_side_google_tag_manager_on_aws_ecs/server_side_google_tag_manager_on_aws_ecs_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = ServerSideGTMFargateStack(app, "server-side-google-tag-manager-on-aws-ecs")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
