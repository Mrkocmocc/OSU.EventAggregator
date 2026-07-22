import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
from app.models import Event
from app import db
import re

logger = logging.getLogger(__name__)

class DodParser:
    BASE_URL = 'http://abiturient.osu.ru'
    DOD_URL = f'{BASE_URL}/step1/dod'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OSU-EventAggregator/1.0'
        })
    
    def parse(self):
        try:
            logger.info("Начинаем парсинг мероприятий ДОД")
            response = self.session.get(self.DOD_URL, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            events = self._extract_events(soup)
            
            logger.info(f"Извлечено {len(events)} мероприятий ДОД")
            return events
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге ДОД: {e}")
            return []
    
    def _extract_events(self, soup):
        events = []
        table = soup.find('table', class_='mark_border')
        if not table:
            logger.warning("Таблица с мероприятиями не найдена")
            return events
        
        rows = table.find_all('tr')
        if len(rows) < 2:
            logger.warning("Таблица не содержит данных")
            return events
        
        current_date = None
        rowspan_remaining = 0
        
        for row in rows[1:]: 
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            
            first_cell = cells[0]
            if first_cell.get('rowspan'):
                rowspan = int(first_cell.get('rowspan'))
                current_date = first_cell.get_text(strip=True)
                rowspan_remaining = rowspan - 1
                if len(cells) >= 3:
                    faculty_cell = cells[1]
                    time_place_cell = cells[2]
                else:
                    continue
            else:
                if rowspan_remaining > 0:
                    if len(cells) >= 2:
                        faculty_cell = cells[0]
                        time_place_cell = cells[1]
                        rowspan_remaining -= 1
                    else:
                        continue
                else:
                    if len(cells) >= 3:
                        current_date = first_cell.get_text(strip=True)
                        faculty_cell = cells[1]
                        time_place_cell = cells[2]
                    else:
                        continue
            
            if current_date is None:
                continue
            
            faculty_text = faculty_cell.get_text(separator=' ', strip=True)
            time_place_text = time_place_cell.get_text(separator=' ', strip=True)
            
            faculty_text = re.sub(r'\s+', ' ', faculty_text).strip()
            time_place_text = re.sub(r'\s+', ' ', time_place_text).strip()
            
            time_match = re.search(r'(\d{1,2}:\d{2})', time_place_text)
            time_str = time_match.group(1) if time_match else None
            location = time_place_text.replace(time_str, '').strip() if time_str else time_place_text
            location = re.sub(r',\s*', ', ', location) 
            
            description = ''
            italic_tags = faculty_cell.find_all('i')
            if italic_tags:
                description = ' '.join([t.get_text(strip=True) for t in italic_tags])
                for italic in italic_tags:
                    italic.extract()
                faculty_text = faculty_cell.get_text(separator=' ', strip=True)
                faculty_text = re.sub(r'\s+', ' ', faculty_text).strip()
            
            event_date = self._parse_date(current_date)
            if not event_date:
                continue
            
            if time_str:
                try:
                    hour, minute = map(int, time_str.split(':'))
                    event_date = event_date.replace(hour=hour, minute=minute)
                except (ValueError, TypeError):
                    pass
            
            event_type = self._determine_event_type(faculty_text, description)
            
            external_id = self._build_external_id(current_date, faculty_text, time_str)
            
            event_data = {
                'external_id': external_id,
                'title': f"День открытых дверей: {faculty_text}",
                'description': description or faculty_text,
                'event_date': event_date,
                'location': location,
                'event_type': event_type,
                'source_url': self.DOD_URL,
                'source_name': 'Дни открытых дверей ОГУ'
            }
            events.append(event_data)
        
        return events
    
    def _parse_date(self, date_text):
        try:
            patterns = [
                r'(\d{2})\.(\d{2})\.(\d{4})',
                r'(\d{1,2})\.(\d{2})\.(\d{4})',
                r'(\d{2})\.(\d{2})\.(\d{2})',
            ]
            for pattern in patterns:
                match = re.search(pattern, date_text)
                if match:
                    day, month, year = match.groups()
                    day = int(day)
                    month = int(month)
                    year = int(year)
                    if year < 100:
                        year += 2000
                    return datetime(year, month, day)
            logger.warning(f"Не удалось распарсить дату: {date_text}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при парсинге даты {date_text}: {e}")
            return None
    
    def _determine_event_type(self, faculty_text, description):
        keywords = {
            'квиз': 'викторина',
            'презентация': 'презентация',
            'экскурсия': 'экскурсия',
            'тренинг': 'тренинг',
            'семинар': 'семинар',
            'мастер-класс': 'мастер-класс',
            'лекция': 'лекция'
        }
        combined = (faculty_text + ' ' + description).lower()
        for kw, typ in keywords.items():
            if kw in combined:
                return typ
        return 'день открытых дверей'
    
    def _build_external_id(self, date_text, faculty_text, time_str):
        date_clean = re.sub(r'[^\d]', '', date_text)
        faculty_clean = re.sub(r'[^a-zA-Zа-яА-Я0-9]+', '_', faculty_text.lower())
        time_clean = re.sub(r'[^\d]', '', time_str) if time_str else '0000'
        return f"dod_{date_clean}_{faculty_clean}_{time_clean}"
    
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
        logger.info(f"Сохранено {saved_count} новых и обновлено {updated_count} мероприятий")
        return saved_count, updated_count