import requests
from art import *
import re
import os
from pprint import pprint
from urllib.parse import unquote
from html import unescape

from InquirerPy import inquirer
from InquirerPy import prompt
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

os.system('cls' if os.name == 'nt' else 'clear')
tprint('Breaking_BadFlows')


sensible = ["Broken Changes", "Broken Change", "Breaking Changes", "Breaking Change", "Breaking", "Broken"]

def get_requester(url, headers=None):
    """Fetches the content of a URL.

    Args:
        url (str): The URL to fetch.
        headers (dict, optional): The headers to send with the request. Defaults to None.

    Returns:
        requests.models.Response: The response object.
    """
    default_headers = {
        'accept': 'application/json',
        'accept-language': 'fr,en-US;q=0.9,en;q=0.8,de;q=0.7',
        'priority': 'u=1, i',
        'referer': 'https://github.com/',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 Chrome/131.0.0.0 Safari/537.36',
        'x-github-target': 'dotcom',
        'x-react-router': 'json',
    }
    if headers:
        default_headers.update(headers)
    response = requests.get(url, headers=default_headers)
    return response

def get_repository_name():
    """Prompts the user to enter the name of the repository to scrape.

    Returns:
        str: The name of the repository to scrape.
    """
    return input("Which repository do you want to scrape? ")

def search_github_repositories(repository_name):
    """Fetches the repositories matching the given name.

    Args:
        repository_name (str): The name of the repository to search for.

    Returns:
        str: The name of the repository to scrape.
    """
    url = f'https://github.com/search?q={repository_name}&type=repositories'

    print(f'\nSearching for repositories matching: "{repository_name}"...')
    headers = {
        'accept': 'application/json',
    }
    response = get_requester(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        repo_names = []

        def grep_hl_name(data):
            if isinstance(data, dict):
                for key, value in data.items():
                    if key == 'hl_name':
                        clean_value = re.sub(r'</?em>', '', value)
                        clean_value = unescape(unquote(clean_value))
                        repo_names.append(clean_value)
                    grep_hl_name(value)
            elif isinstance(data, list):
                for item in data:
                    grep_hl_name(item)

            grep_hl_name(data)

        repo_names.append(Separator('--------------------'))
        repo_names.append('Others')

        if repo_names:
            questions = [
                {
                    'type': 'list',
                    'name': 'repository',
                    'message': "Which repository do you want to scrape?",
                    'choices': repo_names,
                }
            ]
            answers = prompt(questions)
            if answers['repository'] != 'Others':
                print("Selected repository:", answers['repository'])
                return unquote(answers['repository'])

            else:
                repo_url = input("- Enter the full URI of the repository: ")
                repo_name = repo_url.replace('https://github.com/', '')
                repo_name = repo_name[:-1] if repo_name.endswith('/') else repo_name

                print("\nSelected repository:", repo_name)
                return repo_name
        else:
            print("No repositories found.")
    
    else:
        print(f"Failed to fetch data. HTTP Status Code: {response.status_code}")

def isolate_tags(repository_name):
    """Isolates the tags of the given repository.

    Args:
        repository_name (str): The name of the repository to scrape.

    Returns:
        list: The tags of the repository
    """
    url = f'https://github.com/{repository_name}/tags'
    headers = {
        'accept': 'text/html',
    }
    response = get_requester(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tags = soup.find_all('a', href=re.compile(f'/{repository_name}/releases/tag/'))

        tag_names = [tag.text.strip() for tag in tags]
        tag_names = [tag for tag in tag_names if not tag.startswith('Notes') and not tag.startswith('Compare') and not tag.startswith('Downloads')]
        try:
            if tag_names:
                print(f'    - Latest version is: {tag_names[0]}')
            else:
                print("    - No tags found.")
        except IndexError:
            print("    - No tags found.")
        return tag_names
    else:
        print(f"Failed to fetch tags. HTTP Status Code: {response.status_code}")
        return []

def fetch_page(repository_name, page, headers):
    """Fetches a page of release notes.

    Args:
        repository_name (str): The name of the repository to scrape.
        page (int): The page number to fetch.
        headers (dict): The headers to send with the request.

    Returns:
        list: The release notes of the page.
    """
    url = f'https://github.com/{repository_name}/releases/?page={page}'
    response = get_requester(url, headers=headers)
    if response and response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        release_notes = soup.find_all('div', class_='markdown-body')
        results = []
        for release_note in release_notes:
            if any(term in release_note.text for term in sensible):
                tag = release_note.find_previous('h2', class_='sr-only').text
                results.append(tag)
        return results
    return []

def get_release_notes(repository_name):
    """Fetches the release notes of the given repository.

    Args:
        repository_name (str): The name of the repository to scrape.
    """
    url = f'https://github.com/{repository_name}/releases/'
    headers = {'accept': 'text/html'}
    response = get_requester(url, headers=headers)
    
    if response and response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        if soup.find('h2', class_='mb-1') and soup.find('h2', class_='mb-1').text == 'There aren’t any releases here':
            print("    - No releases found.")
            return
        pages = soup.find_all('a', attrs={'aria-label': re.compile(r'Page \d+')})
        last_page = int(pages[-1].text) if pages else 1
        print(f'    - {last_page} pages of releases found.')

        scrapme = input('Do you want to scrap all the pages? (Y/n) ')
        if scrapme.lower() not in ['n', 'no']:
            print('    - Scraping all pages...')
            results = []

            with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust the number of threads as needed
                futures = {executor.submit(fetch_page, repository_name, page, headers): page for page in range(1, last_page + 1)}
                for future in as_completed(futures):
                    page = futures[future]
                    try:
                        data = future.result()
                        results.extend(data)
                        print(f'    - {round((page / last_page) * 100)}% complete', end='\r')
                    except Exception as e:
                        print(f'Error processing page {page}: {e}')
            
            if results:
                print("\nBreaking changes found in the following tags:")
                for tag in results:
                    formatted_tag = re.sub(r'^(.*?)(\d+\.\d+\.\d+)(.*?)$', r'(v)\2', tag).replace('(v)', 'v')
                    print(f"  - {formatted_tag} - URL : https://github.com/{repository_name}/releases/tag/{formatted_tag}")

            else:
                print("No breaking changes found in any release notes.")
                ask_changelog = input("\nDo you want to check within the ChangeLog instead ? (Y/n) ")
                if ask_changelog not in ['no', 'n']:
                    builderurl = f"https://raw.githubusercontent.com/{repository_name}/refs/heads/main/CHANGELOG.md"
                    print(f'    Tentative on : {builderurl}')

                    headers = {'accept': 'text/html'}
                    response = get_requester(builderurl, headers=headers)
                                        
                    if response and response.status_code == 200:
                        changelog_content = response.text
                        breaking_changes = [
                            line for line in changelog_content.splitlines() 
                            if any(re.search(term, line, re.IGNORECASE) for term in sensible)
                        ]

                        if breaking_changes:
                            print("Breaking changes found in the ChangeLog!")
                            for change in breaking_changes:
                                print(f"- {change.strip()}")

                        else:
                            print("No breaking changes found in the ChangeLog.")
                    else:
                        print(f"Failed to fetch the ChangeLog. HTTP Status Code: {response.status_code}")


if __name__ == "__main__":
    repository_name = get_repository_name()
    answer = search_github_repositories(repository_name)
    if answer:
        isolate_tags(answer)
        get_release_notes(answer)