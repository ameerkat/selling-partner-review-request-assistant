##
## Email Address Settings
##

ses_send_from_address = None
ses_send_to_address = None

##
## SP API Developer Settings
##

# This is the first part of the LWA credentials from the developer console
# and is specific to the application you set up.
client_id = None

# This is the hidden part of the LWA credentials from the developer console
client_secret = None

# This is what you get after you click Authorize to initate a self authorization
# for this specific application.
refresh_token = None

##
## AWS Credentials
##

# If you aren't in a lambda you need to fill out the following 3 items
# You also don't need the first two if you have system wide credentials
# set up for AWS e.g. via `aws configure`
access_key = None
secret_key = None
registered_role_arn = None

# Rainforest API Key
rainforest_api_key = None
product_asin = None

# Facebook Ads
facebook_access_token = None
facebook_app_secret = None
facebook_app_id = None
facebook_ad_set_id = None