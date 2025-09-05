import requests
import pandas as pd
import json
import time
import random
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
import logging
from fake_useragent import UserAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JobCrawler:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        
        # Rotate user agents for better success rate
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Job keywords to search for
        self.job_keywords = [
            'devops engineer',
            'senior devops engineer',
            'cloud engineer',
            'senior cloud engineer',
            'infrastructure engineer',
            'senior infrastructure engineer'
        ]
        
        # Career page indicators
        self.career_indicators = [
            'careers', 'career', 'jobs', 'job', 'work-with-us', 'join-us',
            'opportunities', 'employment', 'hiring', 'vacancies', 'positions'
        ]
        
        # Telegram configuration
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Progress tracking files (NO GIT OPERATIONS)
        self.processed_file = 'processed_companies.json'
        self.failed_file = 'failed_companies.json'
        
        self.load_processed_companies()
        self.load_failed_companies()
    
    def load_processed_companies(self):
        """Load the list of successfully processed companies"""
        try:
            if os.path.exists(self.processed_file):
                with open(self.processed_file, 'r') as f:
                    self.processed_companies = json.load(f)
            else:
                self.processed_companies = []
            logger.info(f"Loaded {len(self.processed_companies)} processed companies")
        except Exception as e:
            logger.error(f"Error loading processed companies: {e}")
            self.processed_companies = []
    
    def save_processed_companies(self):
        """Save the list of processed companies (FILE ONLY)"""
        try:
            with open(self.processed_file, 'w') as f:
                json.dump(self.processed_companies, f, indent=2)
            logger.info(f"Saved {len(self.processed_companies)} processed companies")
        except Exception as e:
            logger.error(f"Error saving processed companies: {e}")
    
    def load_failed_companies(self):
        """Load the list of companies that failed processing"""
        try:
            if os.path.exists(self.failed_file):
                with open(self.failed_file, 'r') as f:
                    self.failed_companies = json.load(f)
            else:
                self.failed_companies = {}
            logger.info(f"Loaded {len(self.failed_companies)} failed companies")
        except Exception as e:
            logger.error(f"Error loading failed companies: {e}")
            self.failed_companies = {}
    
    def save_failed_companies(self):
        """Save the list of failed companies (FILE ONLY)"""
        try:
            with open(self.failed_file, 'w') as f:
                json.dump(self.failed_companies, f, indent=2)
            logger.info(f"Saved {len(self.failed_companies)} failed companies")
        except Exception as e:
            logger.error(f"Error saving failed companies: {e}")
    
    def should_retry_company(self, company_name):
        """Check if we should retry a previously failed company"""
        if company_name not in self.failed_companies:
            return True
        
        retry_count = self.failed_companies[company_name].get('count', 0)
        # Retry up to 3 times, then skip
        return retry_count < 3
    
    def send_telegram_notification(self, message):
        """Send notification via Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not configured")
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
            else:
                logger.error(f"Failed to send Telegram notification: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
    
    def clean_company_name(self, company_name):
        """Clean company name for better domain matching"""
        # Remove common suffixes
        suffixes = ['ltd', 'limited', 'plc', 'inc', 'corp', 'corporation', 'group', 'holdings', 'uk', 'technology', 'tech', 'digital', 'systems']
        clean = company_name.lower()
        
        for suffix in suffixes:
            clean = re.sub(rf'\b{suffix}\b', '', clean)
        
        # Remove extra spaces and special characters
        clean = re.sub(r'[^\w\s-]', '', clean).strip()
        clean = re.sub(r'\s+', ' ', clean)
        
        return clean
    
    def try_direct_domains(self, clean_name, original_name):
        """Try various domain patterns"""
        # Generate multiple domain variations
        variations = [
            clean_name.replace(' ', ''),
            clean_name.replace(' ', '-'),
            original_name.lower().replace(' ', ''),
            original_name.lower().replace(' ', '-'),
            ''.join(word[0] for word in clean_name.split()),  # acronym
        ]
        
        extensions = ['.com', '.co.uk', '.uk', '.org']
        
        for variation in variations:
            if not variation:
                continue
                
            for ext in extensions:
                domain = f"{variation}{ext}"
                try:
                    response = self.session.head(f"https://{domain}", timeout=8, allow_redirects=True)
                    if response.status_code == 200:
                        # Verify it's actually the company by checking page content
                        if self.verify_company_website(f"https://{domain}", original_name):
                            logger.info(f"Found direct domain: {domain}")
                            return f"https://{domain}"
                except:
                    continue
        return None
    
    def verify_company_website(self, url, company_name):
        """Verify if the website actually belongs to the company"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return False
                
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text().lower()
            title = soup.find('title')
            
            # Check if company name appears in title or page content
            company_words = company_name.lower().split()
            matches = sum(1 for word in company_words if len(word) > 2 and word in page_text)
            
            # If at least half the company name words appear, consider it a match
            return matches >= len(company_words) / 2
            
        except:
            return True  # If we can't verify, assume it's correct
    
    def search_duckduckgo(self, company_name):
        """Search for company using DuckDuckGo"""
        try:
            query = f"{company_name} official website UK"
            search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            
            response = self.session.get(search_url, timeout=15)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find search result links
            result_links = soup.find_all('a', {'class': 'result__url'})
            
            for link in result_links[:5]:  # Check top 5 results
                href = link.get('href', '')
                if href.startswith('http'):
                    # Clean the URL
                    clean_url = href.split('?')[0]  # Remove query parameters
                    
                    # Skip social media and directory sites
                    skip_domains = ['facebook.com', 'twitter.com', 'linkedin.com', 'wikipedia.org', 
                                  'companies.house.gov.uk', 'companieshouse.gov.uk']
                    
                    if not any(skip in clean_url for skip in skip_domains):
                        if self.verify_company_website(clean_url, company_name):
                            logger.info(f"Found via DuckDuckGo: {clean_url}")
                            return clean_url
            
            return None
            
        except Exception as e:
            logger.error(f"DuckDuckGo search failed for {company_name}: {e}")
            return None
    
    def search_wikipedia(self, company_name):
        """Search Wikipedia for company official website"""
        try:
            # Search Wikipedia
            wiki_search_url = f"https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': f"{company_name} company UK",
                'srlimit': 3
            }
            
            response = self.session.get(wiki_search_url, params=params, timeout=10)
            if response.status_code != 200:
                return None
                
            data = response.json()
            
            # Check each search result
            for result in data.get('query', {}).get('search', []):
                page_title = result['title']
                
                # Get the Wikipedia page content
                page_url = f"https://en.wikipedia.org/w/api.php"
                page_params = {
                    'action': 'query',
                    'format': 'json',
                    'prop': 'extracts|externallinks',
                    'titles': page_title,
                    'exintro': True,
                    'explaintext': True,
                    'elquery': '*',
                    'ellimit': 10
                }
                
                page_response = self.session.get(page_url, params=page_params, timeout=10)
                if page_response.status_code == 200:
                    page_data = page_response.json()
                    pages = page_data.get('query', {}).get('pages', {})
                    
                    for page_id, page_info in pages.items():
                        # Check external links for official website
                        external_links = page_info.get('externallinks', [])
                        
                        for link in external_links:
                            if any(domain in link for domain in ['.com', '.co.uk', '.uk']):
                                # Skip social media
                                if not any(social in link for social in ['facebook', 'twitter', 'linkedin']):
                                    clean_link = link.split('?')[0]
                                    if self.verify_company_website(clean_link, company_name):
                                        logger.info(f"Found via Wikipedia: {clean_link}")
                                        return clean_link
            
            return None
            
        except Exception as e:
            logger.error(f"Wikipedia search failed for {company_name}: {e}")
            return None
    
    def get_company_website(self, company_name):
        """Search for company's official website using multiple strategies"""
        try:
            # Clean company name for better matching
            clean_name = self.clean_company_name(company_name)
            
            # Strategy 1: Try direct domain patterns
            website = self.try_direct_domains(clean_name, company_name)
            if website:
                return website
            
            # Strategy 2: Search using DuckDuckGo
            website = self.search_duckduckgo(company_name)
            if website:
                return website
            
            # Strategy 3: Try Wikipedia search (often has official links)
            website = self.search_wikipedia(company_name)
            if website:
                return website
                
            logger.warning(f"Could not find website for {company_name} using any method")
            return None
            
        except Exception as e:
            logger.error(f"Error getting website for {company_name}: {e}")
            return None
    
    def find_career_pages(self, base_url):
        """Find career pages on the website"""
        career_urls = []
        
        try:
            response = self.session.get(base_url, timeout=15)
            if response.status_code != 200:
                return career_urls
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for career links
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '').lower()
                text = link.get_text().lower()
                
                # Check if link or text contains career indicators
                for indicator in self.career_indicators:
                    if indicator in href or indicator in text:
                        full_url = urljoin(base_url, link.get('href'))
                        if full_url not in career_urls:
                            career_urls.append(full_url)
                        break
            
            # Also check common career page URLs
            common_paths = ['/careers', '/career', '/jobs', '/job-opportunities']
            for path in common_paths:
                career_url = urljoin(base_url, path)
                try:
                    response = self.session.head(career_url, timeout=10)
                    if response.status_code == 200 and career_url not in career_urls:
                        career_urls.append(career_url)
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error finding career pages for {base_url}: {e}")
        
        return career_urls[:3]  # Limit to 3 career pages per company
    
    def check_job_openings(self, career_url):
        """Check if there are relevant job openings on the career page"""
        try:
            response = self.session.get(career_url, timeout=15)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text().lower()
            
            found_jobs = []
            
            for keyword in self.job_keywords:
                if keyword in page_text:
                    # Try to find the specific job posting
                    job_elements = soup.find_all(['div', 'li', 'h3', 'h4', 'p'], 
                                               string=re.compile(keyword, re.IGNORECASE))
                    
                    if job_elements:
                        found_jobs.append(keyword)
            
            return found_jobs
            
        except Exception as e:
            logger.error(f"Error checking job openings for {career_url}: {e}")
            return []
    
    def process_company(self, company_name):
        """Process a single company"""
        logger.info(f"Processing company: {company_name}")
        
        # Skip if already processed successfully
        if company_name in self.processed_companies:
            logger.info(f"Skipping {company_name} - already processed successfully")
            return None
            
        # Skip if failed too many times
        if not self.should_retry_company(company_name):
            logger.info(f"Skipping {company_name} - failed too many times")
            return None
        
        try:
            # Get company website
            website = self.get_company_website(company_name)
            if not website:
                logger.warning(f"Could not find website for {company_name}")
                # Mark as failed
                if company_name not in self.failed_companies:
                    self.failed_companies[company_name] = {'count': 0, 'reason': 'no_website'}
                self.failed_companies[company_name]['count'] += 1
                return None
            
            logger.info(f"Found website for {company_name}: {website}")
            
            # Find career pages
            career_pages = self.find_career_pages(website)
            if not career_pages:
                logger.warning(f"No career pages found for {company_name}")
                # Mark as failed
                if company_name not in self.failed_companies:
                    self.failed_companies[company_name] = {'count': 0, 'reason': 'no_career_pages'}
                self.failed_companies[company_name]['count'] += 1
                return None
            
            # Check for job openings
            all_found_jobs = []
            for career_url in career_pages:
                found_jobs = self.check_job_openings(career_url)
                if found_jobs:
                    all_found_jobs.extend(found_jobs)
            
            if all_found_jobs:
                result = {
                    'company': company_name,
                    'website': website,
                    'career_pages': career_pages,
                    'found_jobs': list(set(all_found_jobs)),
                    'timestamp': datetime.now().isoformat()
                }
                
                # Send Telegram notification
                message = f"""
🎉 <b>Job Alert!</b>

<b>Company:</b> {company_name}
<b>Website:</b> {website}
<b>Found Positions:</b>
{chr(10).join([f"• {job.title()}" for job in result['found_jobs']])}

<b>Career Pages:</b>
{chr(10).join([f"• {url}" for url in career_pages[:2]])}

<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                self.send_telegram_notification(message.strip())
                logger.info(f"Found job openings at {company_name}: {all_found_jobs}")
                
                # Mark as successfully processed
                self.processed_companies.append(company_name)
                return result
            else:
                logger.info(f"No relevant job openings found at {company_name}")
                # Mark as failed (no jobs found)
                if company_name not in self.failed_companies:
                    self.failed_companies[company_name] = {'count': 0, 'reason': 'no_jobs'}
                self.failed_companies[company_name]['count'] += 1
                return None
                
        except Exception as e:
            logger.error(f"Error processing {company_name}: {e}")
            # Mark as failed
            if company_name not in self.failed_companies:
                self.failed_companies[company_name] = {'count': 0, 'reason': 'error'}
            self.failed_companies[company_name]['count'] += 1
            self.failed_companies[company_name]['last_error'] = str(e)
            return None
    
    def run(self, excel_file, max_companies=10):
        """Main execution function - NO GIT OPERATIONS"""
        logger.info(f"Starting job crawler - processing up to {max_companies} companies")
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Assume company names are in the first column
            company_column = df.columns[0]
            companies = df[company_column].dropna().tolist()
            
            # Filter out already processed companies
            unprocessed_companies = [c for c in companies if c not in self.processed_companies]
            
            if not unprocessed_companies:
                logger.info("All companies have been processed. Resetting processed list.")
                self.processed_companies = []
                unprocessed_companies = companies
            
            # Process companies (up to max_companies)
            companies_to_process = unprocessed_companies[:max_companies]
            results = []
            
            for i, company in enumerate(companies_to_process):
                logger.info(f"Processing {i+1}/{len(companies_to_process)}: {company}")
                
                result = self.process_company(company)
                if result:
                    results.append(result)
                
                # Save progress after each company (FILES ONLY - NO GIT)
                self.save_processed_companies()
                self.save_failed_companies()
                
                # Add shorter delay between requests to be respectful but efficient
                time.sleep(random.uniform(1, 3))
            
            logger.info(f"Completed processing. Found jobs at {len(results)} companies.")
            
            # Send summary notification
            if results:
                summary = f"""
📊 <b>Crawling Summary</b>

<b>Companies Processed:</b> {len(companies_to_process)}
<b>Jobs Found:</b> {len(results)}

<b>Companies with Openings:</b>
{chr(10).join([f"• {r['company']}" for r in results])}
                """
                self.send_telegram_notification(summary.strip())
            
            # Print final statistics
            print(f"=== FINAL STATISTICS ===")
            print(f"Total processed companies: {len(self.processed_companies)}")
            print(f"Total failed companies: {len(self.failed_companies)}")
            print(f"Jobs found in this run: {len(results)}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in main execution: {e}")
            self.send_telegram_notification(f"❌ Job crawler encountered an error: {str(e)}")
            return []

if __name__ == "__main__":
    crawler = JobCrawler()
    
    # Get Excel file path from environment variable or use default
    excel_file = os.getenv('EXCEL_FILE', 'companies.xlsx')
    
    if not os.path.exists(excel_file):
        logger.error(f"Excel file not found: {excel_file}")
        exit(1)
    
    # Run crawler (NO GIT OPERATIONS ANYWHERE)
    results = crawler.run(excel_file, max_companies=10)
    
    print(f"Crawling completed. Found jobs at {len(results)} companies.")
