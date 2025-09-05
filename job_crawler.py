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
        
        # Processed companies tracking file
        self.processed_file = 'processed_companies.json'
        self.load_processed_companies()
        
    def load_processed_companies(self):
        """Load the list of already processed companies"""
        try:
            if os.path.exists(self.processed_file):
                with open(self.processed_file, 'r') as f:
                    self.processed_companies = json.load(f)
            else:
                self.processed_companies = []
        except Exception as e:
            logger.error(f"Error loading processed companies: {e}")
            self.processed_companies = []
    
    def save_processed_companies(self):
        """Save the list of processed companies"""
        try:
            with open(self.processed_file, 'w') as f:
                json.dump(self.processed_companies, f)
        except Exception as e:
            logger.error(f"Error saving processed companies: {e}")
    
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
    
    def get_company_website(self, company_name):
        """Search for company's official website using Google search simulation"""
        try:
            # Simple approach: try common domain patterns
            domain_patterns = [
                f"{company_name.lower().replace(' ', '')}.com",
                f"{company_name.lower().replace(' ', '')}.co.uk",
                f"{company_name.lower().replace(' ', '-')}.com",
                f"{company_name.lower().replace(' ', '-')}.co.uk"
            ]
            
            for domain in domain_patterns:
                try:
                    response = self.session.head(f"https://{domain}", timeout=10, allow_redirects=True)
                    if response.status_code == 200:
                        return f"https://{domain}"
                except:
                    continue
            
            # If direct patterns don't work, try a simple search approach
            # Note: In production, you might want to use a proper search API
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
        
        # Skip if already processed
        if company_name in self.processed_companies:
            logger.info(f"Skipping {company_name} - already processed")
            return None
        
        try:
            # Get company website
            website = self.get_company_website(company_name)
            if not website:
                logger.warning(f"Could not find website for {company_name}")
                self.processed_companies.append(company_name)
                return None
            
            logger.info(f"Found website for {company_name}: {website}")
            
            # Find career pages
            career_pages = self.find_career_pages(website)
            if not career_pages:
                logger.warning(f"No career pages found for {company_name}")
                self.processed_companies.append(company_name)
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
                
                self.processed_companies.append(company_name)
                return result
            else:
                logger.info(f"No relevant job openings found at {company_name}")
                self.processed_companies.append(company_name)
                return None
                
        except Exception as e:
            logger.error(f"Error processing {company_name}: {e}")
            self.processed_companies.append(company_name)
            return None
    
    def run(self, excel_file, max_companies=10):
        """Main execution function"""
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
                
                # Save progress after each company
                self.save_processed_companies()
                
                # Add delay between requests to be respectful
                time.sleep(random.uniform(2, 5))
            
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
    
    # Run crawler
    results = crawler.run(excel_file, max_companies=10)
    
    print(f"Crawling completed. Found jobs at {len(results)} companies.")
