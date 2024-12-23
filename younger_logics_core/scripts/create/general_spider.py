import scrapy
from scrapy.crawler import CrawlerProcess

from paperswithcode import PapersWithCodeClient
from tea_client.errors import HttpClientError

import json
from tqdm import tqdm
import time
import copy
import threading
from datetime import datetime


# const var
ITEMS_PER_PAGE = 400
# DATE_SHRESHOLD = datetime.strptime('2024-11-20', '%Y-%m-%d')
FIRST_KEYWORD = 'evaluations'  # 'repositories' 'tasks' 'datasets' 'methods' 'results'
SECOND_KEYWORD = 'results'

# cnt
parse_cnt = 0

# initial
start_time = time.time()
var_lock = threading.Lock()
list_lock = threading.Lock()
list2_lock = threading.Lock()
client = PapersWithCodeClient()

# output
out_dict = {}
url_spider_record = []
url_spider_all = []

# input
in_start_url_list = []


# spider class
class JsonDownloader(scrapy.Spider):
    name = "json_downloader"
    start_urls = []

    def __init__(self, url_list=None, *args, **kwargs):
        super(JsonDownloader, self).__init__(*args, **kwargs)
        if url_list is not None:
            self.start_urls = url_list

    def parse(self, response):
        global out_dict, parse_cnt, url_spider_record, url_spider_all
        # cnt ++
        self.add_parse_cnt()
        # get data
        json_data = response.json()
        # get info from url
        page_number = int(response.url.split('&')[1].split('=')[1])
        with list_lock:
            url_spider_record.append(response.url)
        # TODO need to be modify
        out_dict_key = ''
        if FIRST_KEYWORD == 'repositories':
            owner = response.url.split('/')[6]
            name = response.url.split('/')[7]
            out_dict_key = owner + ' / ' + name
        elif FIRST_KEYWORD in ['papers', 'areas', 'tasks', 'datasets', 'evaluations']:
            out_dict_key = response.url.split('/')[6]
        else:
            raise Exception
        # process by page_number
        if page_number == 1:
            if json_data['count'] != 0:
                new_urls, page_num = self.extract_new_urls(json_data['count'], response.url)
                out_dict[out_dict_key] = {'count': json_data['count'], 'results': [json_data['results']] + [[]] * page_num}
                with list2_lock:
                    url_spider_all.extend(new_urls)
                for new_url in new_urls:
                    yield scrapy.Request(url=new_url, callback=self.parse)
        else:
            out_dict[out_dict_key]['results'][page_number - 1] = json_data['results']

    def add_parse_cnt(self):
        global parse_cnt
        with var_lock:
            parse_cnt += 1
            if parse_cnt % 10 == 0:
                print(f'parse_cnt is {parse_cnt}')

    def extract_new_urls(self, item_num: int, first_url: str):
        new_urls = []
        if item_num <= ITEMS_PER_PAGE:
            return new_urls, 0
        page_num = (item_num - 1) // ITEMS_PER_PAGE
        segs = first_url.split('&')
        for page_number in range(2, page_num + 2):
            segs[1] = f'page={page_number}'
            new_urls.append(copy.deepcopy('&'.join(segs)))
        return new_urls, page_num


# get data
if FIRST_KEYWORD == 'repositories':
    with open('./data/id_file/repo_owner_list.json', 'r') as f:
        repo_owner_list = json.load(f)
    with open('./data/id_file/repo_name_list.json', 'r') as f:
        repo_name_list = json.load(f)
    for i in range(len(repo_owner_list)):
        repo_owner = repo_owner_list[i]
        repo_name = repo_name_list[i]
        in_start_url_list.append(
            f'https://paperswithcode.com/api/v1/{FIRST_KEYWORD}/{repo_owner}/{repo_name}/{SECOND_KEYWORD}/?format=json&page=1&ordering=id&items_per_page={ITEMS_PER_PAGE}')
elif FIRST_KEYWORD == 'papers':
    with open('./data/id_file/paper_id_list.json', 'r') as f:
        paper_id_list = json.load(f)
    for paper_id in paper_id_list:
        in_start_url_list.append(
            f'https://paperswithcode.com/api/v1/{FIRST_KEYWORD}/{paper_id}/{SECOND_KEYWORD}/?format=json&page=1&ordering=id&items_per_page={ITEMS_PER_PAGE}')
elif FIRST_KEYWORD == 'areas':
    with open('./data/id_file/area_id_list.json', 'r') as f:
        area_id_list = json.load(f)
    for area_id in area_id_list:
        in_start_url_list.append(
            f'https://paperswithcode.com/api/v1/{FIRST_KEYWORD}/{area_id}/{SECOND_KEYWORD}/?format=json&page=1&ordering=id&items_per_page={ITEMS_PER_PAGE}')
elif FIRST_KEYWORD == 'tasks':
    with open('./data/id_file/task_id_list.json', 'r') as f:
        task_id_list = json.load(f)
    for task_id in task_id_list:
        in_start_url_list.append(
            f'https://paperswithcode.com/api/v1/{FIRST_KEYWORD}/{task_id}/{SECOND_KEYWORD}/?format=json&page=1&ordering=id&items_per_page={ITEMS_PER_PAGE}')
elif FIRST_KEYWORD == 'datasets':
    with open('./data/id_file/dataset_id_list.json', 'r') as f:
        dataset_id_list = json.load(f)
    for dataset_id in dataset_id_list:
        in_start_url_list.append(
            f'https://paperswithcode.com/api/v1/{FIRST_KEYWORD}/{dataset_id}/{SECOND_KEYWORD}/?format=json&page=1&ordering=id&items_per_page={ITEMS_PER_PAGE}')
elif FIRST_KEYWORD == 'evaluations':
    with open('./data/id_file/evaluation_id_list.json', 'r') as f:
        evaluation_id_list = json.load(f)
    for evaluation_id in evaluation_id_list:
        in_start_url_list.append(
            f'https://paperswithcode.com/api/v1/{FIRST_KEYWORD}/{evaluation_id}/{SECOND_KEYWORD}/?format=json&page=1&ordering=id&items_per_page={ITEMS_PER_PAGE}')


# start spider
process = CrawlerProcess(settings={
    'CONCURRENT_REQUESTS': 16,  # 设置并发请求数量
    'RETRY_TIMES': 3,  # 设置重试次数
})
process.crawl(JsonDownloader, url_list=in_start_url_list)
process.start()

# reduce
try:
    for key, value in out_dict.items():
        tmp = [item for sublist in value['results'] for item in sublist]
        out_dict[key]['results'] = tmp
except Exception as e:
    print('reduce exception !!!')

with open(f'./data/{FIRST_KEYWORD}_to_{SECOND_KEYWORD}.json', 'w') as f:
    json.dump(out_dict, f, indent=4)

with open(f'./data_backup/{FIRST_KEYWORD}_to_{SECOND_KEYWORD}.json', 'w') as f:
    json.dump(out_dict, f, indent=4)

try:
    with open(f'./data/spider_record/{FIRST_KEYWORD}_to_{SECOND_KEYWORD}_record.json', 'w') as f:
        json.dump(url_spider_record, f, indent=4)
    with open(f'./data_backup/{FIRST_KEYWORD}_to_{SECOND_KEYWORD}_record.json', 'w') as f:
        json.dump(url_spider_record, f, indent=4)
    with open(f'./data/spider_record/{FIRST_KEYWORD}_to_{SECOND_KEYWORD}_all.json', 'w') as f:
        json.dump(url_spider_all, f, indent=4)
    with open(f'./data_backup/{FIRST_KEYWORD}_to_{SECOND_KEYWORD}_all.json', 'w') as f:
        json.dump(url_spider_all, f, indent=4)
except Exception as e:
    print(f'record save error !!!')

# final
end_time = time.time()
print(f'total time is {end_time - start_time}')
