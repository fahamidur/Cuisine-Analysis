# scrapper.py
import csv
import json
import time
import math
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup

def scrape_cuisines():
    """Scrape cuisine list and save to CSV"""
    # Setup browser
    driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()))
    
    # Open page
    url = "https://www.allrecipes.com/cuisine-a-z-6740455"
    driver.get(url)
    time.sleep(5)

    # Find cuisine elements
    elements = driver.find_elements(By.CSS_SELECTOR, "a.mntl-link-list__link")

    # Prepare data
    data = []
    for el in elements:
        name = el.text.strip()
        link = el.get_attribute("href")
        data.append([name, link])

    # Save to CSV
    with open("cuisines.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Country", "Link"])  # header
        writer.writerows(data)

    print("Data saved to cuisines.csv")
    driver.quit()

def scrape_recipes():
    """Scrape recipes for each cuisine and save to JSON"""
    # Read CSV
    csv_file = "cuisines.csv"
    country_links = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_links.append({
                "Country": row["Country"],
                "CuisineLink": row["Link"]
            })

    # Setup Selenium
    options = Options()
    options.set_preference("dom.webnotifications.enabled", False)
    driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=options)
    all_data = []

    def scroll_to_bottom(driver, pause=1, max_attempts=20):
        last_height = driver.execute_script("return document.body.scrollHeight")
        attempts = 0
        while attempts < max_attempts:
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(pause)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height > last_height:
                last_height = new_height
                attempts = 0
            else:
                attempts += 1

    def close_pushly_popup(driver):
        try:
            dismiss_btn = driver.find_element(By.CSS_SELECTOR, "button.pushly-prompt-btn-dismiss")
            dismiss_btn.click()
            print("Popup dismissed")
            time.sleep(1)
        except:
            pass

    # Loop through country links
    for entry in country_links:
        country = entry["Country"]
        link = entry["CuisineLink"]
        print(f"Scraping {country} -> {link}")
        driver.get(link)
        time.sleep(2)
        close_pushly_popup(driver)

        scroll_to_bottom(driver, pause=0.5)
        time.sleep(5)
        close_pushly_popup(driver)

        cards = driver.find_elements(By.CSS_SELECTOR, "a.mntl-card-list-items")
        for card in cards:
            try:
                recipe_link = card.get_attribute("href")
                name_el = card.find_element(By.CSS_SELECTOR, "span.card__title-text")
                name = name_el.text.strip()

                all_data.append({
                    "Country": country,
                    "Cuisine": name,
                    "Link": recipe_link
                })
            except Exception as e:
                print("Skipped a card:", e)
                continue

    # Save to JSON
    with open("cuisines_recipes.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4)

    print(f"Saved {len(all_data)} recipes to cuisines_recipes.json")
    driver.quit()

def enhance_recipes():
    """Extract detailed information for each recipe"""
    start_time = time.time()

    # Load JSON file
    with open("cuisines_recipes.json", "r", encoding="utf-8") as f:
        recipes_data = json.load(f)

    # Create fully headless Firefox driver
    def create_driver():
        options = Options()
        options.add_argument("--headless")
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("dom.push.enabled", False)
        driver = webdriver.Firefox(
            service=Service(GeckoDriverManager().install()),
            options=options
        )
        return driver

    # Extract recipe details
    def extract_recipe_details(recipe, driver):
        print(f"Scraping: {recipe['Cuisine']} | {recipe['Link']}")
        details = {
            "total_time": "N/A",
            "servings": "N/A",
            "ingredients": [],
            "nutrition_facts": {},
            "total_rating": "N/A",
            "rating_count": "N/A"
        }

        try:
            driver.get(recipe["Link"])
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Total Time & Servings
            for item in soup.find_all("div", class_="mm-recipes-details__item"):
                label = item.find("div", class_="mm-recipes-details__label")
                value = item.find("div", class_="mm-recipes-details__value")
                if label and value:
                    label_text = label.text.strip().lower()
                    if "total time" in label_text:
                        details["total_time"] = value.text.strip()
                    elif "servings" in label_text:
                        details["servings"] = value.text.strip()

            # Ingredients
            ingredients_list = soup.find("ul", class_="mm-recipes-structured-ingredients__list")
            if ingredients_list:
                for li in ingredients_list.find_all("li", class_="mm-recipes-structured-ingredients__list-item"):
                    details["ingredients"].append(li.get_text(strip=True))

            # Nutrition Facts
            table = soup.find("table", class_="mm-recipes-nutrition-facts-summary__table")
            if table:
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        details["nutrition_facts"][cells[1].get_text(strip=True)] = cells[0].get_text(strip=True)

            # Ratings
            rating_div = soup.find("div", id=lambda x: x and "mm-recipes-review-bar__rating_" in x)
            if rating_div:
                details["total_rating"] = rating_div.get_text(strip=True)

            rating_count_div = soup.find("div", id=lambda x: x and "mm-recipes-review-bar__rating-count_" in x)
            if rating_count_div:
                details["rating_count"] = rating_count_div.get_text(strip=True).replace("(", "").replace(")", "")

            print(f"Success: {recipe['Cuisine']} | Rating: {details['total_rating']} ({details['rating_count']})")

        except Exception as e:
            print(f"✗ FAILED {recipe['Cuisine']}: {e}")

        return {
            "Country": recipe["Country"],
            "Cuisine": recipe["Cuisine"],
            "Link": recipe["Link"],
            "Total_Time": details["total_time"],
            "Servings": details["servings"],
            "Ingredients": details["ingredients"],
            "Nutrition_Facts": details["nutrition_facts"],
            "Total_Rating": details["total_rating"],
            "Rating_Count": details["rating_count"]
        }

    # Split into 5 parts
    num_parts = 5
    part_size = math.ceil(len(recipes_data) / num_parts)

    driver = create_driver()

    for part in range(num_parts):
        start_idx = part * part_size
        end_idx = min((part + 1) * part_size, len(recipes_data))
        part_recipes = recipes_data[start_idx:end_idx]
        enhanced_recipes = []

        print(f"\n--- Processing Part {part + 1}/{num_parts} ({start_idx} to {end_idx}) ---\n")
        
        for recipe in part_recipes:
            result = extract_recipe_details(recipe, driver)
            enhanced_recipes.append(result)

        # Save after each part
        filename = f"enhanced_recipes_part_{part + 1}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(enhanced_recipes, f, indent=4, ensure_ascii=False)
        print(f"\nSaved Part {part + 1} to '{filename}'\n")

    driver.quit()
    end_time = time.time()
    print(f"\nAll parts complete! Total time: {end_time - start_time:.2f} seconds")

def main():
    """Main function to run the scraping pipeline"""
    print("Starting cuisine scraping...")
    scrape_cuisines()
    
    print("\nStarting recipe scraping...")
    scrape_recipes()
    
    print("\nStarting recipe enhancement...")
    enhance_recipes()
    
    print("\nScraping completed successfully!")

if __name__ == "__main__":
    main()