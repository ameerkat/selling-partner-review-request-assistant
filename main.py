from secrets import *

##
## Config
##
# Modify this if you want to change configurations, configurations
# are not stored anywhere else. In order for these to apply you
# will have to upload this to lambda unless you are running this script
# locally.
##

# This is used to determine order eligibility, note that this should
# be between 4 and 29 (30 is the max on Amazon). The optimal setting
# for this would depend on your product and your own research.
minimum_order_age_days = 15

# Set this to true will prevent the script from actually soliciting reviews
# this can let you test that you have everything set up correctly without
# triggering a review request.
dryrun = False

# Constants
MAXIMUM_ELIGIBLE_DAYS = 30       # Will not search orders older than this
MARKETPLACE_ID = "ATVPDKIKX0DER" # US marketplace, refer https://docs.developer.amazonservices.com/en_US/dev_guide/DG_Endpoints.html
# This is the only solicitation type available right now refer https://github.com/amzn/selling-partner-api-docs/blob/main/references/solicitations-api/solicitations.md
REVIEW_SOLICITATION_TYPE = "productReviewAndSellerFeedbackSolicitation"
CURRENT_TABLE_VERSION = "1"      # Bumping this will create a new table
                                 # This isn't a problem as the API will return 403 for orders with existing review solicitations
METADATA_VERSION = "1"           # The version of the non-key data stored as "metadata_version" in the ddb table
SP_API_HOST = "sellingpartnerapi-na.amazon.com"
SCRIPT_SELF_IDENTIFIER = "ReviewRequestAssistance 0.1" # Used as the user-agent
# Name prefix of the DDB table, this isn't the full name as the full name is this + "_" + table version
ddb_cache_table_name = "WishboneSolicitationRequests"  

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

def ensure_table_existence(ddb, table_name):
    try:
        response = ddb.describe_table(TableName=table_name)
    except ddb.exceptions.ResourceNotFoundException:
        print(f"Table {table_name} does not exist, creating table.")
        ddb.create_table(
            TableName=table_name,
            KeySchema=[
            {
                'AttributeName': 'order_id',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'solicitation_type',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'order_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'solicitation_type',
                'AttributeType': 'S'
            }
        ],
        BillingMode='PAY_PER_REQUEST')
        print(f"✔ Table {table_name} created successfully.")

def check_solicitation_existence(ddb, table_name, order_id, solicitation_type):
    try:
        result = ddb.get_item(TableName=table_name, Key={'order_id': {"S": order_id}, 'solicitation_type': {"S": solicitation_type}})
        if "Item" not in result:
            return False
        return True
    except ddb.exceptions.ResourceNotFoundException:
        return False

def put_solicitation_existence(ddb, table_name, order_id, solicitation_type):
    ddb.put_item(TableName=table_name, Item={
            'order_id': {"S": order_id},
            'solicitation_type': {"S": solicitation_type},
            'metadata_version': {"N": METADATA_VERSION},
            'date_created_utc': {"S": datetime.utcnow().isoformat()}
        })

def scan_and_solicit(event, context): 
    if dryrun:
        print("NOTICE: THIS IS A DRYRUN ☀")
    if context: # is in a lambda
        sts = boto3.client('sts', region_name ="us-east-1")
        ddb = boto3.client('dynamodb', region_name ="us-east-1")
        request = Sigv4Request(region="us-east-1")    
    else:
        sts = boto3.client('sts', region_name ="us-east-1", aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        ddb = boto3.client('dynamodb', region_name ="us-east-1", aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        assumed_role = sts.assume_role(RoleArn=registered_role_arn, RoleSessionName="review-request-assistant")
        role_access_key = assumed_role["Credentials"]["AccessKeyId"]
        role_secret_key = assumed_role["Credentials"]["SecretAccessKey"]
        role_session_token = assumed_role["Credentials"]["SessionToken"]
        print("✔ Assumed role successfully.")
        request = Sigv4Request(region="us-east-1", access_key=role_access_key, secret_key=role_secret_key, session_token=role_session_token)

    access_token = get_lwa_access_token(client_id, client_secret, refresh_token)
    created_before = (datetime.utcnow() - timedelta(days=minimum_order_age_days)).isoformat()
    created_after = (datetime.utcnow() - timedelta(days=MAXIMUM_ELIGIBLE_DAYS)).isoformat()
    print(f"Requesting orders created between {created_after} and {created_before}")
    
    orders = []
    has_next = True
    next_token = None
    while has_next:
        next_token_param = f"&NextToken={next_token}" if next_token else ""
        order_request_url = f'https://{SP_API_HOST}/orders/v0/orders?MarketplaceIds={MARKETPLACE_ID}&CreatedAfter={created_after}&CreatedBefore={created_before}{next_token_param}'
        orders_response = request.get(
            url=order_request_url, 
            headers={'x-amz-access-token': access_token, 'user-agent': SCRIPT_SELF_IDENTIFIER})
        orders_json = json.loads(orders_response.content)
        orders += orders_json["payload"]["Orders"]
        if "NextToken" in orders_json["payload"]:
            has_next = True
            next_token = urllib.parse.quote_plus(orders_json["payload"]["NextToken"])
            time.sleep(0.1) # artificially delay
        else:
            has_next = False
            next_token = None
    num_orders = len(orders)
    print(f"Retrieved {num_orders} orders", [order["AmazonOrderId"] for order in orders])
    print("Requesting feedback for orders.")
    full_table_name = f"{ddb_cache_table_name}_{CURRENT_TABLE_VERSION}"
    ensure_table_existence(ddb, full_table_name)
    orders_requested = []
    for order in orders:
        order_id = order["AmazonOrderId"]
        previous_solicitation = check_solicitation_existence(ddb, full_table_name, order_id, REVIEW_SOLICITATION_TYPE)
        if not previous_solicitation:
            if not dryrun:
                solicitation_response = request.post(
                    url=f'https://{SP_API_HOST}/solicitations/v1/orders/{order_id}/solicitations/productReviewAndSellerFeedback?marketplaceIds={MARKETPLACE_ID}', 
                    headers={'x-amz-access-token': access_token, 'user-agent': SCRIPT_SELF_IDENTIFIER})
                print(solicitation_response)
                time.sleep(1) # to limit to 1 TPS as per documentation
            orders_requested.append(order_id)
            put_solicitation_existence(ddb, full_table_name, order_id, REVIEW_SOLICITATION_TYPE)
    print("Requested for orders", orders_requested)

if __name__ == "__main__":
    scan_and_solicit(None, None)