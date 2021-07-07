import requests

def get_product_data(asin, rainforest_api_key = None, amazon_domain = "amazon.com"):
    product_url = f"https://api.rainforestapi.com/request?api_key={rainforest_api_key}&type=product&asin={asin}&amazon_domain={amazon_domain}"
    product_data = requests.get(product_url).json()
    return product_data["product"]