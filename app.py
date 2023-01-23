#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.gtm_fargate_stack import ServerSideGoogleTagManagerFargateStack


app = cdk.App()
ServerSideGoogleTagManagerFargateStack(app, "ServerSideGoogleTagManagerFargateStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
    )

app.synth()
