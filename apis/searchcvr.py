import os
import httpx
import json
import re
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

# Load environment variables
# Falls back to the current working directory if `.env` is not found
load_dotenv()

# Get auth credentials from environment variables
AUTH_USERNAME = os.getenv("AUTH_USERNAME")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

if not AUTH_USERNAME or not AUTH_PASSWORD:
    raise ValueError("AUTH_USERNAME and AUTH_PASSWORD environment variables must be set")

# API endpoint
API_URL = "http://distribution.virk.dk/cvr-permanent/virksomhed/_search"

# Create a reusable HTTP client with proper configuration
http_client = httpx.Client(
    timeout=30.0,  # Increased timeout for better reliability
    auth=(AUTH_USERNAME, AUTH_PASSWORD),
    headers={"Content-Type": "application/json"}
)

class CVRAPIError(Exception):
    """Custom exception for CVR API errors"""
    pass

def handle_api_response(response: httpx.Response) -> dict:
    """Handle API response and raise appropriate exceptions"""
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": "NOT_FOUND"}
        raise CVRAPIError(f"HTTP error occurred: {str(e)}")
    except httpx.RequestError as e:
        raise CVRAPIError(f"Request failed: {str(e)}")
    except json.JSONDecodeError as e:
        raise CVRAPIError(f"Invalid JSON response: {str(e)}")

def search_cvr_api(cvr_number: int) -> dict:
    """Look up company information based on CVR number."""
    payload = {
        "_source": ["Vrvirksomhed"],
        "query": {"term": {"Vrvirksomhed.cvrNummer": cvr_number}},
    }
    
    try:
        response = http_client.post(API_URL, json=payload)
        json_response = handle_api_response(response)

        if json_response["hits"]["total"] == 0:
            return {"error": "NOT_FOUND"}
        
        company = json_response["hits"]["hits"][0]["_source"]["Vrvirksomhed"]
        return format_company_data(company, cvr_number)
    except CVRAPIError as e:
        return {"error": str(e)}

def search_cvr_by_name(company_name: str) -> List[Dict]:
    """Search for companies matching the provided name."""
    payload = {
        "_source": ["Vrvirksomhed"],
        "query": {
            "match_phrase_prefix": {
                "Vrvirksomhed.virksomhedMetadata.nyesteNavn.navn": company_name
            }
        },
        "size": 100,
    }

    try:
        response = http_client.post(API_URL, json=payload)
        json_response = handle_api_response(response)

        companies = []
        for hit in json_response["hits"]["hits"]:
            company = hit["_source"]["Vrvirksomhed"]
            cvr_number = company["cvrNummer"]
            formatted_company = format_company_data(company, cvr_number)
            companies.append(formatted_company)
        return companies
    except CVRAPIError as e:
        return [{"error": str(e)}]

def search_cvr_by_fuzzy_name(company_name: str) -> List[Dict]:
    """Return companies matching the name using fuzzy search."""
    payload = {
        "_source": ["Vrvirksomhed"],
        "query": {
            "multi_match": {
                "query": company_name,
                "fields": ["Vrvirksomhed.virksomhedMetadata.nyesteNavn.navn^2"],
                "fuzziness": "AUTO",
            }
        },
        "size": 100,
    }

    try:
        response = http_client.post(API_URL, json=payload)
        json_response = handle_api_response(response)

        companies = []
        for hit in json_response.get("hits", {}).get("hits", []):
            company = hit["_source"].get("Vrvirksomhed", {})
            cvr_number = company.get("cvrNummer")

            metadata = company.get("virksomhedMetadata", {})
            nyeste_navn = metadata.get("nyesteNavn", {})
            hovedbranche = metadata.get("nyesteHovedbranche", {}) or {}

            formatted_company = {
                "name": nyeste_navn.get("navn", "Unknown"),
                "cvr_number": cvr_number,
                "industrycode": hovedbranche.get("branchekode", "Unknown"),
                "industrytext": hovedbranche.get("branchetekst", "Unknown"),
            }
            companies.append(formatted_company)
        return companies
    except CVRAPIError as e:
        return [{"error": str(e)}]

def search_cvr_by_email(email: str) -> List[Dict]:
    """Find companies registered with the given email address."""
    payload = {
        "_source": ["*"],
        "query": {
            "match": {"Vrvirksomhed.elektroniskPost.kontaktoplysning": email}
        },
        "size": 100,
    }

    try:
        response = http_client.post(API_URL, json=payload)
        json_response = handle_api_response(response)

        companies = []
        for hit in json_response["hits"]["hits"]:
            company = hit["_source"]["Vrvirksomhed"]
            cvr_number = company["cvrNummer"]
            formatted_company = format_company_data(company, cvr_number)
            companies.append(formatted_company)
        return companies
    except CVRAPIError as e:
        return [{"error": str(e)}]

def search_cvr_by_email_domain(email_domain: str) -> List[Dict]:
    """Search for companies by matching email domain."""
    email = "@" + email_domain
    payload = {
        "_source": ["*"],
        "query": {
            "match": {"Vrvirksomhed.elektroniskPost.kontaktoplysning": email}
        },
        "size": 100,
    }

    try:
        response = http_client.post(API_URL, json=payload)
        json_response = handle_api_response(response)

        companies = []
        for hit in json_response["hits"]["hits"]:
            company = hit["_source"]["Vrvirksomhed"]
            cvr_number = company["cvrNummer"]
            formatted_company = format_company_data(company, cvr_number)
            companies.append(formatted_company)
        return companies
    except CVRAPIError as e:
        return [{"error": str(e)}]

def search_cvr_by_phone(phone_number: str) -> List[Dict]:
    """Locate companies by phone number."""
    payload = {
        "_source": ["*"],
        "query": {
            "match": {"Vrvirksomhed.telefonNummer.kontaktoplysning": phone_number}
        },
        "size": 100,
    }

    try:
        response = http_client.post(API_URL, json=payload)
        json_response = handle_api_response(response)

        companies = []
        for hit in json_response["hits"]["hits"]:
            company = hit["_source"]["Vrvirksomhed"]
            cvr_number = company["cvrNummer"]
            formatted_company = format_company_data(company, cvr_number)
            companies.append(formatted_company)
        return companies
    except CVRAPIError as e:
        return [{"error": str(e)}]

# Format company data
def format_company_data(company: dict, cvr_number: str) -> dict:
    """Convert raw company data to the API response schema."""
    company_data = {
        "vat": cvr_number,
        "name": get_company_name(company),
        "address": get_combined_address(company),
        "zipcode": get_address_field(company, "postnummer"),
        "city": get_address_field(company, "postdistrikt"),
        "cityname": get_address_field(company, "bynavn"),
        "protected": company.get("reklamebeskyttet"),
        "phone": get_phone_number(company),
        "email": get_email(company),
        "fax": company.get("telefaxNummer"),
        "startdate": get_formatted_date(
            company["virksomhedMetadata"]["stiftelsesDato"]
        ),
        "enddate": (
            get_formatted_date(company["livsforloeb"][0]["periode"]["gyldigTil"])
            if "gyldigTil" in company["livsforloeb"][0]["periode"]
            else None
        ),
        "employees": get_employees(company),
        "addressco": get_address_field(company, "conavn"),
        "industrycode": company["virksomhedMetadata"]["nyesteHovedbranche"][
            "branchekode"
        ],
        "industrydesc": company["virksomhedMetadata"]["nyesteHovedbranche"][
            "branchetekst"
        ],
        "companycode": company["virksomhedMetadata"]["nyesteVirksomhedsform"][
            "virksomhedsformkode"
        ],
        "companydesc": company["virksomhedMetadata"]["nyesteVirksomhedsform"][
            "langBeskrivelse"
        ],
        "bankrupt": is_bankrupt(company),
        "status": company["virksomhedMetadata"]["sammensatStatus"],
        "companytypeshort": company["virksomhedMetadata"]["nyesteVirksomhedsform"][
            "kortBeskrivelse"
        ],
        "website": get_website(company),
        "version": 1,
    }
    return company_data

# Get company name
def get_company_name(company):
    return company["virksomhedMetadata"]["nyesteNavn"]["navn"]

# Get combined address
def get_combined_address(company):
    address = company["virksomhedMetadata"]["nyesteBeliggenhedsadresse"]
    combined_address = f"{address['vejnavn']} {address.get('husnummerFra', '')}"

    if address.get("husnummerTil"):
        combined_address += f"-{address['husnummerTil']}"

    combined_address += address.get("bogstavFra", "") or ""

    if address.get("bogstavTil"):
        combined_address += f"-{address['bogstavTil']}"

    combined_address += f", {address['etage']}" if address.get("etage") else ""

    return combined_address

# Get specific field from address
def get_address_field(company, field):
    address = company["virksomhedMetadata"]["nyesteBeliggenhedsadresse"]
    return address.get(field)

# Get formatted date
def get_formatted_date(date):
    if date is None:
        return None
    parts = date.split("-")
    return f"{parts[2]}/{parts[1]} - {parts[0]}"

# Get phone number
def get_phone_number(company):
    contact_info = company["virksomhedMetadata"]["nyesteKontaktoplysninger"]
    phone = re.findall(r"\b\d{8}\b", str(contact_info))
    return phone[0] if phone else None

# Get email
def get_email(company):
    contact_info = company["virksomhedMetadata"]["nyesteKontaktoplysninger"]
    email = re.findall(r"\b[\w.-]+@[\w.-]+\b", str(contact_info))
    return email[0] if email else None

# Get website
def get_website(company):
    contact_info = company["virksomhedMetadata"]["nyesteKontaktoplysninger"]
    website = re.findall(
        r"\bhttp[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+\b",
        str(contact_info),
    )
    return website[0] if website else None

# Get number of employees
def get_employees(company):
    metadata = company.get("virksomhedMetadata", {})
    erst_maaned_beskaeftigelse = metadata.get("nyesteErstMaanedsbeskaeftigelse")
    if erst_maaned_beskaeftigelse:
        return erst_maaned_beskaeftigelse.get("antalAnsatte")
    return None

# Check if the company is bankrupt
def is_bankrupt(company):
    metadata = company.get("virksomhedMetadata")
    if metadata:
        nyeste_status = metadata.get("nyesteStatus")
        if nyeste_status:
            return nyeste_status.get("kreditoplysningtekst") == "Konkurs"
    return False
