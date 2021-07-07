from copy import Error
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
minimum_order_age_days = 20

# Set this to true will prevent the script from actually soliciting reviews
# this can let you test that you have everything set up correctly without
# triggering a review request.
dryrun = True

##
## Primary Script
##

import boto3
import secrets
import logging
from datetime import datetime, timedelta
from solicit_reviews import scan_and_solicit
from product import get_product_data
from orders import get_recent_orders
from advertising import get_advertising_metadata

def main(event, context):
    is_lambda = True if context else False
    result = scan_and_solicit(
        minimum_order_age_days, 
        secrets.client_id, 
        secrets.client_secret, 
        secrets.refresh_token, 
        dryrun = dryrun, 
        is_lambda = is_lambda,
        access_key = secrets.access_key,
        secret_key = secrets.secret_key,
        registered_role_arn=secrets.registered_role_arn)
    review_solicitation_count = len(result)

    product_data = get_product_data(secrets.product_asin, secrets.rainforest_api_key)

    ses = boto3.client('ses', region_name ="us-east-1") if is_lambda else boto3.client(
        'ses', region_name ="us-east-1", aws_access_key_id=secrets.access_key, aws_secret_access_key=secrets.secret_key)
    
    recent_orders_after = (datetime.utcnow() - timedelta(days=1))
    recent_orders = get_recent_orders(recent_orders_after, 
        secrets.client_id, 
        secrets.client_secret, 
        secrets.refresh_token, 
        is_lambda = is_lambda,
        access_key = secrets.access_key,
        secret_key = secrets.secret_key,
        registered_role_arn=secrets.registered_role_arn)
    orders_html = ""
    total_units = 0
    for order in recent_orders:
        total_units += order['NumberOfItemsShipped'] + order['NumberOfItemsUnshipped']
        orders_html += f"{order['AmazonOrderId']} - {order['NumberOfItemsShipped']} Shipped / {order['NumberOfItemsUnshipped']} Unshipped - Purchase Date {order['PurchaseDate']}<br />"
    if not orders_html:
        orders_html += "<i>No recent orders</i>"

    # Facebook
    facebook_ads_html_block = ""
    try:
        facebook_ad_metadata = get_advertising_metadata(secrets.facebook_access_token, secrets.facebook_ad_set_id)[0]
        total_ad_spend = facebook_ad_metadata["spend"]
        cost_per_click = next((x["value"] for x in facebook_ad_metadata["cost_per_action_type"] if x["action_type"] == "link_click"), None)
        cost_per_conversion = next((x["value"] for x in facebook_ad_metadata["cost_per_action_type"] if x["action_type"] == "lead"), None)
        facebook_ads_html_block = f"""
                    <span style="font-size: 8pt">Total Spend</span> ${total_ad_spend}<br />
                    <span style="font-size: 8pt">Cost Per Click</span> ${cost_per_click}<br />
                    <span style="font-size: 8pt">Cost Per Lead</span> ${cost_per_conversion}<br />
        """
    except Error:
       facebook_ads_html_block = "<i>Failed to load Facebook Ads Data</i>" 

    current_date = datetime.utcnow().isoformat()
    sesresponse = ses.send_email(
    Source=secrets.ses_send_from_address,
    Destination={'ToAddresses': [secrets.ses_send_to_address]},
    Message={
        'Subject': {
            'Data': f'FBA Product Status Update - {current_date}',
            'Charset': 'utf-8'
        },
        'Body': {
            'Html': {
                'Data': f"""
                <!DOCTYPE html>
                <html>
                <body>
                    <h2><a href="{product_data["link"]}">{product_data["title"]}</a></h2>
                    <img src="{product_data["main_image"]["link"]}" style="width: 300px" />
                    <p>
                    <h3>Reviews</h3>
                    <span style="font-size: 8pt">Reviews Solicited Today via API</span> {review_solicitation_count}<br />
                    <i>These following are not deltas but absolute values</i><br />
                    <span style="font-size: 8pt">Overall Rating</span> {product_data["rating"]}<br />
                    <span style="font-size: 8pt">Total Reviews</span> {product_data["reviews_total"]}<br />
                    <span style="font-size: 8pt">Total Ratings</span> {product_data["ratings_total"]}<br />

                    <h3>Last 24h Orders ({total_units} Units)</h3>
                    {orders_html}

                    <h3>Facebook (Trailing 3 Days)</h3>
                    {facebook_ads_html_block}
                </body>
                </html>
                """,
                'Charset': 'utf-8'
            }
        }
    })
    logging.debug(sesresponse)

if __name__ == "__main__":
    main(None, None)