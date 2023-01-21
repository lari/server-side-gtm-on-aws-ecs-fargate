#!/usr/bin/env python3
import os

import aws_cdk as cdk

from server_side_google_tag_manager_on_aws_ecs.server_side_google_tag_manager_on_aws_ecs_stack import ServerSideGoogleTagManagerOnAwsEcsStack


app = cdk.App()
ServerSideGoogleTagManagerOnAwsEcsStack(app, "ServerSideGoogleTagManagerOnAwsEcsStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
