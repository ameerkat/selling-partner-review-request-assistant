##
## Config
##

# Constants
MARKETPLACE_ID = "ATVPDKIKX0DER" # US marketplace, refer https://docs.developer.amazonservices.com/en_US/dev_guide/DG_Endpoints.html
# This is the only solicitation type available right now refer https://github.com/amzn/selling-partner-api-docs/blob/main/references/solicitations-api/solicitations.md
SP_API_HOST = "sellingpartnerapi-na.amazon.com"
SCRIPT_SELF_IDENTIFIER = "ReviewRequestAssistance 0.1" # Used as the user-agent

##
## Primary Script
##

from requests_sigv4 import Sigv4Request
import requests
import json
import time
import boto3
from datetime import datetime, timedelta
import urllib.parse
import logging

def get_lwa_access_token(_client_id, _client_secret, _refresh_token):
    response = requests.post(url="https://api.amazon.com/auth/o2/token/", data={
        "grant_type": "refresh_token",
        "refresh_token": _refresh_token,
        "client_id": _client_id,
        "client_secret": _client_secret
    })
    response_json = json.loads(response.content)
    print("✔ Retrieved LWA token successfully.")
    return response_json["access_token"]

def get_recent_orders(created_after,
                        lwa_client_id,
                        lwa_client_secret,
                        lwa_refresh_token,
                        is_lambda = True, 
                        access_key = None, 
                        secret_key = None, 
                        registered_role_arn = None): 
    if is_lambda: # is in a lambda.
        logging.debug("Detected as running in lambda.")
        sts = boto3.client('sts', region_name ="us-east-1")
        request = Sigv4Request(region="us-east-1")    
    else:
        logging.debug("Not running as lambda.")
        sts = boto3.client('sts', region_name ="us-east-1", aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        assumed_role = sts.assume_role(RoleArn=registered_role_arn, RoleSessionName="review-request-assistant")
        role_access_key = assumed_role["Credentials"]["AccessKeyId"]
        role_secret_key = assumed_role["Credentials"]["SecretAccessKey"]
        role_session_token = assumed_role["Credentials"]["SessionToken"]
        logging.debug("✔ Assumed role successfully.")
        request = Sigv4Request(region="us-east-1", access_key=role_access_key, secret_key=role_secret_key, session_token=role_session_token)

    access_token = get_lwa_access_token(lwa_client_id, lwa_client_secret, lwa_refresh_token)
    created_after = created_after.isoformat()
    logging.info(f"Requesting orders created after {created_after}")
    
    orders = []
    has_next = True
    next_token = None
    while has_next:
        next_token_param = f"&NextToken={next_token}" if next_token else ""
        order_request_url = f'https://{SP_API_HOST}/orders/v0/orders?MarketplaceIds={MARKETPLACE_ID}&CreatedAfter={created_after}{next_token_param}'
        orders_response = request.get(
            url=order_request_url, 
            headers={'x-amz-access-token': access_token, 'user-agent': SCRIPT_SELF_IDENTIFIER})
        orders_json = json.loads(orders_response.content)
        orders += orders_json["payload"]["Orders"]
        if "NextToken" in orders_json["payload"]:
            has_next = True
            next_token = urllib.parse.quote_plus(orders_json["payload"]["NextToken"])
            time.sleep(0.1) # to limit to 10 TPS as per documentation
        else:
            has_next = False
            next_token = None
    num_orders = len(orders)
    logging.debug(f"Retrieved {num_orders} orders: " + ",".join([order["AmazonOrderId"] for order in orders]))
    return orders