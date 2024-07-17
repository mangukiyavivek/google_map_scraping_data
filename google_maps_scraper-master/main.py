import os
import sys
import time
import argparse
from dataclasses import dataclass, asdict, field
import pandas as pd
from playwright.sync_api import sync_playwright

@dataclass
class Business:
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None

@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)
    save_at: str = 'output'

    def dataframe(self):
        return pd.json_normalize((asdict(business) for business in self.business_list), sep="_")

    def save_to_excel(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    coordinates = url.split('/@')[-1].split('/')[0]
    return float(coordinates.split(',')[0]), float(coordinates.split(',')[1])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int, default=100)
    args = parser.parse_args()

    search_list = [args.search] if args.search else []
    total = args.total if args.total else 1_000_000

    if not args.search:
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = file.readlines()
        if not search_list:
            print('Error: You must either pass the -s search argument, or add searches to input.txt')
            sys.exit()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(5000)

        business_list = BusinessList()

        for search_for_index, search_for in enumerate(search_list):
            print(f"-----\n{search_for_index} - {search_for}".strip())
            page.locator('//input[@id="searchboxinput"]').fill(search_for.strip())
            page.wait_for_timeout(3000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            locator = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]')

            previously_counted = 0
            max_attempts = 20
            attempts = 0

            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(5000)

                current_count = locator.count()
                if current_count >= total or current_count == previously_counted or attempts >= max_attempts:
                    listings = locator.all()[:total]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    previously_counted = current_count
                    attempts += 1
                    print(f"Currently Scraped: {current_count}")

            for listing in listings:
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    business = Business()

                    name_attribute = 'aria-label'
                    business.name = listing.get_attribute(name_attribute) or ""

                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
                    reviews_average_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'

                    if page.locator(address_xpath).count() > 0:
                        business.address = page.locator(address_xpath).first.inner_text()
                    else:
                        business.address = ""

                    if page.locator(website_xpath).count() > 0:
                        business.website = page.locator(website_xpath).first.inner_text()
                    else:
                        business.website = ""

                    if page.locator(phone_number_xpath).count() > 0:
                        business.phone_number = page.locator(phone_number_xpath).first.inner_text()
                    else:
                        business.phone_number = ""

                    if page.locator(review_count_xpath).count() > 0:
                        business.reviews_count = int(
                            page.locator(review_count_xpath).first.inner_text().split()[0].replace(',', '').strip()
                        )
                    else:
                        business.reviews_count = None

                    if page.locator(reviews_average_xpath).count() > 0:
                        business.reviews_average = float(
                            page.locator(reviews_average_xpath).first.get_attribute(name_attribute).split()[0].replace(',', '.').strip()
                        )
                    else:
                        business.reviews_average = None

                    business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error occurred: {e}')

                if len(business_list.business_list) >= total:
                    break

        filename = f"google_maps_data"
        business_list.save_to_csv(filename)

        browser.close()

if __name__ == "__main__":
    if not any(arg in sys.argv for arg in ['-s', '--search']):
        location = input("Enter the location to search: ")
        sys.argv.extend(['-s', location])
    main()
