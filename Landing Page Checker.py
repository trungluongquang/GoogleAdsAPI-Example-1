from typing import List, Dict
import time
from google.ads.googleads.client import GoogleAdsClient
from socket import gaierror
from google.api_core.exceptions import InternalServerError, Unknown
from google.ads.googleads.errors import GoogleAdsException
from urllib.error import URLError
from bs4 import BeautifulSoup
import requests


# in this example, we use Google Ads API v9. For the `google-ads.yaml`, read the README.md for more details.
# `google-ads.yaml` cannot be shared public
GA_CLIENT = GoogleAdsClient.load_from_storage(version='v9', path='google-ads.yaml')
GA_SERVICE = GA_CLIENT.get_service('GoogleAdsService')


def query_ads(customer_id: str, retry: bool = False):
    """
    Query all eligible ads from Google Ads.
    At the time this program is written (December 2021), Expanded Text Ads has not been sunset yet
    :param customer_id: account ID
    :param retry: True if it is a retry (recursive)
    :return:
    """
    query = f"""
            SELECT
                campaign.name,
                campaign.id,
                ad_group.campaign,
                ad_group.name,
                ad_group.id,
                ad_group_ad.policy_summary.review_status,
                ad_group_ad.ad.id,
                ad_group_ad.ad.final_urls
            FROM ad_group_ad
            WHERE ad_group_ad.ad.type IN ('EXPANDED_TEXT_AD', 'RESPONSIVE_SEARCH_AD')
            AND campaign.status = ENABLED
            AND campaign.serving_status NOT IN ('ENDED', 'SUSPENDED')
            AND ad_group.status = ENABLED
            AND ad_group_ad.status = ENABLED"""
    try:
        return GA_SERVICE.search_stream(customer_id=customer_id, query=query)
    except AttributeError as e:
        if retry is True:
            raise AttributeError
        else:
            # if it is the first time we get error, we wait for x seconds and retry
            print(f'{customer_id} - AttributeError - {e}')
            time.sleep(45)
            query_ads(customer_id=customer_id, retry=True)


def get_all_urls(customer_id: str) -> Dict[str, Dict[str, str]]:
    """
    get all urls from the account along with the campaign name and ad group. Each URL is stored once
    utm parameter is stripped so that the return urls only contain the main part
    :param customer_id:
    :return:
    """
    result = dict()
    ad_response = query_ads(customer_id=customer_id)
    for batch in ad_response:
        for row in batch.results:
            url = row.ad_group_ad.ad.final_urls[0].split('?')[0]
            result[url] = {
                'Campaign': row.campaign.name,
                'AdGroup': row.ad_group.name
            }
    return result


def get_response_from_url(url: str, retry: bool = False):
    """
    open the url get response. If it fails, try again in 30 seconds. If it still fails return None
    :param url:
    :param retry: True if it is a retry
    :return:
    """
    try:
        return requests.get(url)
    except requests.exceptions.ChunkedEncodingError as e:
        if retry is True:
            time.sleep(30)
            return None
        print(f'{url} - {e}')
        get_response_from_url(url=url, retry=True)
    except requests.exceptions.ConnectionError as e:
        if retry is True:
            time.sleep(30)
            return None
        print(f'{url} - {e}')
        get_response_from_url(url=url, retry=True)


def get_voucher_on_spartwelt_page(url: str):
    """
    crawl the page and get the first voucher on page
    :param url: url to the page where we want to crawl
    :return:
    """
    response = get_response_from_url(url)
    if (response is not None) and response.ok:
        soup = BeautifulSoup(response.content, 'html.parser')
        first_voucher = soup.find_all("div", {"class": "ui-teaser-claim"})[0].getText().replace('\n', ' ').strip()
        first_voucher = ' '.join(first_voucher.split())
        return first_voucher
    return None


def main(countries: List[str]):
    for country in countries:
        print(f'Work with: {country}')
        assert len(country) == 12 and len(country.replace('-', '')) == 10, \
            'A customer ID must have 10 digits and 2 -'
        try:
            all_urls = get_all_urls(customer_id=country.replace('-', ''))
            for url, campaign_adgroup in all_urls.items():
                url = 'https://www.sparwelt.de/gutscheine/adidas-shop'  # a sample URL
                first_voucher = get_voucher_on_spartwelt_page(url=url)
                print(f"{campaign_adgroup['Campaign']} - {campaign_adgroup['AdGroup']} - {first_voucher}")
        except InternalServerError as e:
            print(f'{country} - GoogleInternalServerError {e}')
            continue
        except Unknown as e:
            print(f'{country} - Unknown Google Error {e}')
            continue
        except GoogleAdsException as e:
            print(f'{country} - GoogleAdsException {e}')
            continue
        except gaierror as e:
            print(f'{country} - socket.gaierror: {e}')
            continue
        except URLError as e:
            print(f'{country} - urllib.error.URLError: {e}')
            continue
        except AttributeError as e:
            print(f'{country} - AttributeError {e}')
            continue


if __name__ == "__main__":
    countries = [
        'xxx-xxx-xxxx'  # NOTE: replace this with a Google Customer ID
    ]
    main(countries)
