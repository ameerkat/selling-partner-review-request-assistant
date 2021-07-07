# This is a facebook advertising module

import secrets

from facebook_business.adobjects.adset import AdSet
from facebook_business.api import FacebookAdsApi

def get_advertising_metadata(access_token, facebook_ad_set_id):
  FacebookAdsApi.init(access_token=access_token)

  fields = [
    'cost_per_action_type',
    'spend'
  ]

  params = {
    'date_preset': 'last_3d'
  }

  return AdSet(facebook_ad_set_id).get_insights(
    fields=fields,
    params=params,
  )

if __name__ == "__main__":
  print(get_advertising_metadata(
    secrets.facebook_access_token, 
    secrets.facebook_ad_set_id))