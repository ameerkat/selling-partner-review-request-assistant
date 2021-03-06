##
## SP API Developer Settings
##

# This is the first part of the LWA credentials from the developer console
# and is specific to the application you set up. This looks something like
# "amzn1.application-oa2-client.<hex id>"
client_id = None

# This is the hidden part of the LWA credentials from the developer console
client_secret = None

# This is what you get after you click Authorize to initate a self authorization
# for this specific application in the specific marketplace.
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
