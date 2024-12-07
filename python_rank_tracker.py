import base64
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import random
import streamlit as st
from time import sleep
import zipfile
import os
import json
import io
import re
from geopy.geocoders import Nominatim

# List of user agents for random selection (for mobile and desktop)
mobile_user_agents = [
    "Mozilla/5.0 (Linux; Android 10; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Samsung Galaxy S20) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
]

desktop_user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
]

# Directory to save the HTML files
html_directory = "saved_serp_html"

# Create the directory if it doesn't exist
if not os.path.exists(html_directory):
    os.makedirs(html_directory)

# Function to get IP address and geolocation
def get_ip_and_geolocation():
    try:
        ip_info = requests.get("https://ipinfo.io/json").json()
        ip_address = ip_info.get("ip")
        geolocation = ip_info.get("loc")  # Latitude and Longitude
        city = ip_info.get("city")
        region = ip_info.get("region")
        country = ip_info.get("country")
        return ip_address, geolocation, city, region, country
    except Exception as e:
        st.error(f"Could not fetch IP information: {e}")
        return None, None, None, None, None

# Function to extract mobile snippet results
def extract_mobile_snippet_results(soup, query, domain_to_find):
    snippet_type = None
    snippet_div = soup.find("div", class_="yp1CPe wDYxhc NFQFxe viOShc LKPcQc")
    
    featured_snippet_count = 0

    # Check if there's a featured snippet
    if snippet_div:
        if snippet_div.find("div", class_="di3YZe"):
            snippet_type = "List type featured snippet"
            featured_snippet_count += 1
        elif snippet_div.find("div", class_="LGOjhe", attrs={"data-attrid": "wa:/description"}):
            snippet_type = "Paragraph Featured Snippet"
            featured_snippet_count += 1
        elif snippet_div.find("div", class_="webanswers-webanswers_table__webanswers-table"):
            snippet_type = "Table Featured Snippet"
            featured_snippet_count += 1

    results_list = []
    search_results = soup.find_all("div", class_="yp1CPe wDYxhc NFQFxe viOShc LKPcQc")
    processed_urls = set()

    # Set initial position based on the presence of a featured snippet
    position = 1 if featured_snippet_count > 0 else 0

    for result in search_results:
        title_container = result.find("div", class_="Xv4xee")
        title_element = title_container.find("a", class_="sXtWJb") if title_container else None
        title = title_element.get_text(strip=True) if title_element else "No title"

        link_element = result.find("a", class_="sXtWJb")
        link = link_element.get("href") if link_element else "No link"

        if link not in processed_urls:
            processed_urls.add(link)
            domain_found = "Yes" if domain_to_find and domain_to_find in link else "No"
            results_list.append({
                "Query": query,
                "Position": position,
                "Domain Found": domain_found,
                "Title": title,
                "Link": link,
                "Snippet Type": snippet_type if featured_snippet_count > 0 else ''
            })
            position += 1  # Increase position for each result

    return results_list, position

# Function to extract organic results for mobile
def extract_organic_results_mobile(soup, query, domain_to_find, position):
    results_list = []
    search_results = soup.find_all("div", class_="Ww4FFb vt6azd xpd EtOod pkphOe")
    processed_urls = set()

    for result in search_results:
        nested_div = result.find("div", class_="P8ujBc v5yQqb jqWpsc")
        if not nested_div:
            continue

        link_element = result.find("a", href=True)
        if link_element:
            link = link_element["href"]
            if link.startswith("/url?"):
                link = re.search(r'url=(.*?)(?:&|$)', link).group(1)
                link = requests.utils.unquote(link)

            title_element = result.select_one("div.v7jaNc.ynAwRc")
            title = title_element.get_text(strip=True) if title_element else "No title"

            if link not in processed_urls:
                processed_urls.add(link)
                position += 1  # Increment for each organic result
                domain_found = "Yes" if domain_to_find and domain_to_find in link else "No"
                results_list.append({
                    "Query": query,
                    "Position": position,
                    "Domain Found": domain_found,
                    "Title": title,
                    "Link": link,
                    "Snippet Type": ''
                })

    return results_list

# Function to extract featured snippets for desktop
def extract_results_from_desktop(soup, query, domain_to_find):
    results_list = []
    position = 0

    # Extract featured snippets
    snippet_type = None
    snippet_div = soup.find("div", class_="yp1CPe wDYxhc NFQFxe viOShc LKPcQc")
    featured_snippet_count = 0

    # Initialize values for featured snippet if found
    if snippet_div:
        # Check specific conditions to determine the snippet type
        if snippet_div.find("div", class_="di3YZe"):
            snippet_type = "List type featured snippet"
            featured_snippet_count += 1
        elif snippet_div.find("div", class_="LGOjhe", attrs={"data-attrid": "wa:/description"}):
            snippet_type = "Paragraph Featured Snippet"
            featured_snippet_count += 1
        elif snippet_div.find("div", class_="webanswers-webanswers_table__webanswers-table"):
            snippet_type = "Table Featured Snippet"
            featured_snippet_count += 1
            
        # Extract title and link for the featured snippet
        title_element = snippet_div.find("h3") or snippet_div.find("div", class_="BNeawe s3v9rd AP7Wnd")
        link_element = snippet_div.find("a", href=True)

        title = title_element.get_text(strip=True) if title_element else "No title"
        link = link_element.get("href") if link_element else "N/A"

    # Set initial position based on the presence of a featured snippet
    position = 1 if featured_snippet_count > 0 else 0

    # Add featured snippet results if any
    if featured_snippet_count > 0:
        results_list.append({
            "Query": query,
            "Position": position,
            "Domain Found": "Yes" if domain_to_find and domain_to_find in link else "No",
            "Title": title,
            "Link": link,
            "Snippet Type": snippet_type
        })

    # Extract organic results
    organic_results, position = extract_organic_results_desktop(soup, query, domain_to_find, position)
    results_list.extend(organic_results)

    return results_list, position

# Function to extract results from desktop
def extract_organic_results_desktop(soup, query, domain_to_find, position):
    results_list = []
    search_results = soup.find_all("div", class_="g Ww4FFb vt6azd tF2Cxc asEBEc")
    processed_urls = set()

    for result in search_results:
        link_element = result.find("a", href=True)
        if link_element:
            link = link_element.get("href")
            if link not in processed_urls:
                processed_urls.add(link)
                title_element = result.find("h3")
                title = title_element.get_text() if title_element else "No title"
                domain_found = "Yes" if domain_to_find and domain_to_find in link else "No"
                results_list.append({
                    "Query": query,
                    "Position": position,
                    "Domain Found": domain_found,
                    "Title": title,
                    "Link": link,
                    "Snippet Type": ''
                })
                position += 1  # Increase position for each actual result

    return results_list, position

# Function to encode the location for the uule parameter
def encode_location_for_uule(location):
    encoded_location = base64.urlsafe_b64encode(location.encode()).decode()
    return encoded_location

# Function to get coordinates for a location using geocoding
def get_coordinates(location):
    geolocator = Nominatim(user_agent="your_app_name")  # Specify a user agent
    location_obj = geolocator.geocode(location)
    if location_obj:
        return (location_obj.latitude, location_obj.longitude)
    else:
        st.error(f"Could not geocode the location: {location}")
        return None

# Function to search Google with the uule parameter
def search_google(tld, country, language, results_per_page, queries, domain_to_find, save_html=False, stop_on_domain_found=False, device_type="desktop", max_pages=5):
    results_list = []
    results_df = pd.DataFrame()

    user_agents = desktop_user_agents if device_type == "desktop" else mobile_user_agents
    viewport = "width=device-width, initial-scale=1" if device_type == "mobile" else "width=1024"

    # Dictionary to keep track of position for each query
    query_positions = {query: 0 for query in queries}

    # Specify location to mimic based on user input
    location_to_mimic = f"{country}"  # Format as "Country, Language"
    coordinates = get_coordinates(location_to_mimic)

    if coordinates:
        latitude, longitude = coordinates
        # Create a location string for uule
        location_string = f"ll={latitude},{longitude}"
        uule = encode_location_for_uule(location_string)

        for query in queries:
            st.write(f"Searching for: {query.strip()}")
            encoded_query = quote_plus(query.strip())
            domain_found_in_query = False

            for page in range(max_pages):
                if stop_on_domain_found and domain_found_in_query:
                    break

                start = page * results_per_page
                google_url = f"https://www.{tld}/search?q={encoded_query}&gl={country}&hl={language}&start={start}&pws=0&uule={uule}"

                # Inform the user about the selected country for the search
                st.write(f"Using location for search: {location_to_mimic}")

                attempts = 0
                delay = 5

                while attempts < 3:
                    try:
                        headers = {
                            "User-Agent": random.choice(user_agents),
                            "Viewport": viewport
                        }
                        response = requests.get(google_url, headers=headers)  # Removed proxy usage

                        if response.status_code == 429:
                            st.warning("Too many requests. Pausing for a few seconds before retrying.")
                            sleep(delay)
                            attempts += 1
                            continue

                        response.raise_for_status()

                        if save_html:
                            html_path = os.path.join(html_directory, f"{query.strip().replace(' ', '_')}_SERP_{device_type}_page_{page}.html")
                            with open(html_path, "w", encoding="utf-8") as f:
                                f.write(response.text)
                            st.write(f"SERP HTML saved at: {html_path}")

                        soup = BeautifulSoup(response.text, "html.parser")

                        # Extract results based on device type
                        if device_type == "mobile":
                            page_results, position = extract_mobile_snippet_results(soup, query, domain_to_find)
                            page_results += extract_organic_results_mobile(soup, query, domain_to_find, position)
                        else:
                            page_results, position = extract_results_from_desktop(soup, query, domain_to_find)

                        # Correctly update positions for results
                        for result in page_results:
                            result['Position'] = query_positions[query] + 1  # Start position for this page
                            query_positions[query] += 1  # Increment position for each result

                        results_list.extend(page_results)

                        if stop_on_domain_found and any(result["Domain Found"] == "Yes" for result in page_results):
                            domain_found_in_query = True
                            break

                        st.write(f"Google Search URL: {google_url}")

                        sleep(5)
                        break

                    except requests.exceptions.RequestException as e:
                        st.error(f"Request error: {e}")
                        attempts += 1
                        sleep(5)

    if results_list:
        results_df = pd.DataFrame(results_list)
        results_df = results_df[["Query", "Position", "Domain Found", "Title", "Link", "Snippet Type"]]
        st.session_state.results_df = results_df
    else:
        st.warning("No results were fetched. Please try adjusting your settings or waiting before retrying.")

    return results_df

# Function to zip saved SERP HTML files
def zip_saved_html_files(directory):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".html"):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, directory)
                    zip_file.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

# Streamlit App Execution
if __name__ == "__main__":
    st.title("Google Search Scraper & Rank Tracker")

    # Get user IP and geolocation
    ip_address, geolocation, city, region, country = get_ip_and_geolocation()

    # Display user IP and geolocation information
    if ip_address:
        st.write(f"Your IP Address: {ip_address}")
        st.write(f"Geolocation: {geolocation}")
        st.write(f"City: {city}, Region: {region}, Country: {country}")

    with open("country_codes.json", "r", encoding="utf-8") as f:
        countries = json.load(f)

    with open("country_language_mapping.json", "r", encoding="utf-8") as f:
        country_language_mapping = json.load(f)

    task_type = st.radio("Select Task Type:", ("Google result scrapper", "Rank Tracker"))

    def is_valid_url_or_domain(input_string):
        url_regex = re.compile(
            r'^(https?://)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,}(/.*)?$',
            re.IGNORECASE
        )
        return re.match(url_regex, input_string) is not None

    tld = st.text_input("Enter Google Domain (e.g., google.com):", "google.com")
    selected_country = st.selectbox("Select a country:", list(countries.keys()))
    country_code = countries[selected_country]
    available_languages = country_language_mapping.get(selected_country, {"English": "en"})
    selected_language_name = st.selectbox("Select a language:", list(available_languages.keys()))
    language_code = available_languages.get(selected_language_name, "en")

    result_per_page = 10
    max_pages = st.slider("Select Maximum Pages to Crawl:", min_value=1, max_value=10, value=10)

    queries = st.text_area("Enter the list of keywords separated by commas:", "").split(",")
    save_html = st.checkbox("Save SERP HTML for each query?", False)

    device_type = st.radio("Select Device Type:", ("desktop", "mobile"), index=1)

    if task_type == "Rank Tracker":
        domain_or_url_to_find = st.text_input("Enter the domain or URL you want to track:", "")
        if domain_or_url_to_find.strip() == "":
            st.error("Domain or URL is mandatory for the Rank Tracker.")
            stop_on_domain_found = False
        elif not is_valid_url_or_domain(domain_or_url_to_find):
            st.error("Please enter a valid domain name or URL.")
            stop_on_domain_found = False
        else:
            stop_on_domain_found = True
    else:
        domain_or_url_to_find = ""
        stop_on_domain_found = False

    def filter_rank_tracker_results(results_df):
        filtered_df = results_df[results_df["Domain Found"] == "Yes"]
        filtered_df = filtered_df.loc[filtered_df.groupby("Query")["Position"].idxmin()]
        return filtered_df

    results_df = pd.DataFrame()

    if st.button("Start Search"):
        if stop_on_domain_found:
            with st.spinner("Fetching results..."):
                results_df = search_google(
                    tld, country_code, language_code,
                    result_per_page, queries,
                    domain_or_url_to_find, save_html,
                    stop_on_domain_found, device_type,
                    max_pages
                )
        else:
            with st.spinner("Fetching results..."):
                results_df = search_google(
                    tld, country_code, language_code,
                    result_per_page, queries,
                    "", save_html,
                    stop_on_domain_found, device_type,
                    max_pages
                )

        if task_type == "Rank Tracker":
            results_df = filter_rank_tracker_results(results_df)

        if not results_df.empty:
            st.write(results_df)

            csv_data = results_df.to_csv(index=False)
            st.download_button(
                label="Download as CSV",
                data=csv_data,
                file_name="search_results.csv",
                mime="text/csv"
            )

            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                results_df.to_excel(writer, index=False, sheet_name='Results')
            excel_data = excel_buffer.getvalue()

            st.download_button(
                label="Download as Excel",
                data=excel_data,
                file_name="search_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        if save_html and os.listdir(html_directory):
            st.write("Download SERP HTML files:")
            zip_buffer = zip_saved_html_files(html_directory)
            st.download_button(
                label="Download HTML Files as ZIP",
                data=zip_buffer,
                file_name="serp_html_files.zip",
                mime="application/zip"
            )

        if st.button("Run Another Search"):
            st.session_state.clear()
            st.rerun()
