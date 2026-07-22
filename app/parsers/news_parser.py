import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from app.models import Event
from app import db
import re
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class NewsParser:
    BASE_URL = 'https://www.osu.ru'
    NEWS_URL = f'{BASE_URL}/doc/135/type/2'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OSU-EventAggregator/1.0'
        })
    
    def parse(self, month=None, year=None):
        try:
            url = self.NEWS_URL
            
            if month and year:
                month_str = str(int(month)).zfill(2)
                year_str = str(int(year))
                url = f'{self.NEWS_URL}/month/{month_str}/year/{year_str}'
                logger.info(f"Парсинг новостей за {month_str}.{year_str}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            events = self._extract_events(soup)
            
            for event in events:
                if month and year:
                    if not event.get('event_date'):
                        event['event_date'] = f"{year}-{month}-01"
            
            logger.info(f"Извлечено {len(events)} событий")
            return events
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге новостей: {e}")
            return []
    
    def _extract_events(self, soup):
        events = []
        news_blocks = soup.find_all('div', class_='newsblock')
        
        for block in news_blocks:
            try:
                title_link = block.find('h3', class_='news').find('a')
                if not title_link:
                    continue
                
                title = title_link.text.strip()
                link = title_link.get('href', '')
                full_url = f"{self.BASE_URL}{link}" if link.startswith('/') else link
                
                date_div = block.find('div', class_='newsdate')
                event_date = None
                if date_div:
                    date_text = date_div.find('span').text.strip()
                    try:
                        event_date = datetime.strptime(date_text, '%d.%m.%Y')
                    except ValueError:
                        pass
                
                description = ''
                long_description = self._get_full_description(full_url)
                p_tag = block.find('p')
                if p_tag:
                    description = p_tag.get_text(separator=' ', strip=True)
                
                event_datetime = self._extract_event_datetime(long_description)
                if event_datetime:
                    event_date = event_datetime

                event_data = {
                    'external_id': self._build_external_id(link, title),
                    'title': title,
                    'description': description,
                    'event_date': event_date,
                    'location': self._extract_location(long_description),
                    'event_type': self._determine_event_type(title),
                    'source_url': full_url,
                    'source_name': 'Новости ОГУ'
                }
                events.append(event_data)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке блока новости: {e}")
                continue
        
        return events

    def _get_full_description(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            news_content = soup.find('div', class_='newsblock clear first inside')
            
            if not news_content:
                news_content = soup.find('div', class_='center_col')
            
            if news_content:
                full_description = []
                
                paragraphs = news_content.find_all('p', recursive=True)
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and not any(skip in text.lower() for skip in [
                        'ошибка в тексте', 'поделиться', 'ctrl + enter'
                    ]):
                        full_description.append(text)
                    
                tables = news_content.find_all('table', class_='mark_border')
                for table in tables:
                    table_text = self._extract_table_content(table)
                    if table_text:
                        full_description.append(table_text)
                
                lists = news_content.find_all(['ol', 'ul'])
                for list_elem in lists:
                    list_text = self._extract_list_content(list_elem)
                    if list_text:
                        full_description.append(list_text)
                
                other_content = news_content.find_all(['div', 'span'], recursive=True)
                for elem in other_content:
                    if elem.parent and elem.parent.name in ['p', 'table', 'ol', 'ul']:
                        continue
                    text = elem.get_text(strip=True)
                    if text and len(text) > 50 and not any(skip in text.lower() for skip in [
                        'ошибка в тексте', 'поделиться', 'ctrl + enter', 'яндекс'
                    ]):
                        if not any(text in existing for existing in full_description):
                            full_description.append(text)
                
                if full_description:
                    return ' '.join(full_description)
            
            return ''
            
        except Exception as e:
            logger.error(f"Ошибка при получении полного описания с {url}: {e}")
            return ''
        
    def _extract_table_content(self, table):
        try:
            rows = table.find_all('tr')
            if not rows:
                return ''
            
            table_text = []
            
            headers = rows[0].find_all('th')
            if headers:
                header_text = ' | '.join([h.get_text(strip=True) for h in headers])
                table_text.append(f"Таблица: {header_text}")
            
            for row in rows[1:]:
                cells = row.find_all('td')
                if cells:
                    row_text = ' | '.join([cell.get_text(strip=True) for cell in cells])
                    table_text.append(row_text)
            
            return ' | '.join(table_text) if table_text else ''
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении таблицы: {e}")
            return ''
    
    def _extract_list_content(self, list_elem):
        try:
            items = list_elem.find_all('li')
            if not items:
                return ''
            
            list_text = []
            for i, item in enumerate(items, 1):
                item_text = item.get_text(separator=' ', strip=True)
                
                inner_paragraphs = item.find_all('p')
                if inner_paragraphs:
                    for p in inner_paragraphs:
                        p_text = p.get_text(strip=True)
                        if p_text and p_text not in item_text:
                            item_text += f" ({p_text})"
                
                list_text.append(f"{i}. {item_text}")
            
            return ' | '.join(list_text)
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении списка: {e}")
            return ''


    def _build_external_id(self, link, title):
        slug = link.split('/')[-1].strip() or re.sub(r'[^a-zA-Z0-9]+', '_', title).strip('_')
        return f"news_{slug or 'event'}"

    def _extract_location(self, description):
        match = re.search(r'ауд\.\s*(\d+)', description, re.IGNORECASE)
        if match:
            return f"ауд. {match.group(1)}"
        return None
    
    def _determine_event_type(self, title):
        type_keywords = ['cеминар', 'заседание', 'конкурс', 'cовещание', 'награждение']
        for type in type_keywords:
            if type in title.lower():
                return type
        return None
    
    def _extract_event_datetime(self, description):
        event_datetime = None
        patterns = [
            r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})\s+года?\s+в\s+(\d{1,2}):(\d{2})',
            r'(\d{2})\.(\d{2})\.(\d{2,4})\s+в\s+(\d{1,2}):(\d{2})',
            r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+в\s+(\d{1,2}):(\d{2})',
            r'(\d{1,2}):(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2,4})',
            r'в\s+(\d{1,2}):(\d{2})\s+(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})',
        ]
        
        months_map = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                try:
                    if len(groups) == 5:
                        if groups[1] in months_map: 
                            day = int(groups[0])
                            month = months_map[groups[1].lower()]
                            year = int(groups[2])
                            hour = int(groups[3])
                            minute = int(groups[4])
                        else:
                            day = int(groups[0])
                            month = int(groups[1])
                            year = int(groups[2])
                            hour = int(groups[3])
                            minute = int(groups[4])
                            if year < 100:
                                year += 2000
                    elif len(groups) == 4:
                        if groups[1] in months_map:
                            day = int(groups[0])
                            month = months_map[groups[1].lower()]
                            year = datetime.now().year
                            hour = int(groups[2])
                            minute = int(groups[3])
                        else: 
                            hour = int(groups[0])
                            minute = int(groups[1])
                            day = int(groups[2])
                            month = months_map[groups[3].lower()]
                            year = datetime.now().year
                    else:
                        continue
                    
                    event_datetime = datetime(year, month, day, hour, minute)
                    break
                    
                except Exception as e:
                    logger.error(f"Ошибка при парсинге даты/времени: {e}")
                    continue
        
        return event_datetime



    def save_events(self, events):
        saved_count = 0
        updated_count = 0
        now = datetime.now()

        for event_data in events:
            if event_data.get('event_date') is not None:
                if event_data['event_date'] < now:
                    event_data['is_active'] = False
                else:
                    event_data['is_active'] = True
            else:
                event_data['is_active'] = True

            existing_event = Event.query.filter_by(
                external_id=event_data['external_id']
            ).first()
            if existing_event:
                for key, value in event_data.items():
                    setattr(existing_event, key, value)
                updated_count += 1
            else:
                new_event = Event(**event_data)
                db.session.add(new_event)
                saved_count += 1

        db.session.commit()
        return saved_count, updated_count
