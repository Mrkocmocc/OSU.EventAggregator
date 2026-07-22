from flask import Blueprint, request, jsonify, send_file
from app.models import Event
from app import db
from app.parsers.news_parser import NewsParser
from app.parsers.dod_parser import DodParser
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, distinct
import io
import json
import logging
from app.parsers.news_parser import NewsParser

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

@api_bp.route('/parse', methods=['POST'])
def parse():
    try:
        source = request.args.get('source')
        month = request.args.get('month')
        year = request.args.get('year')
        
        if source == 'news' or source is None:
            if month:
                try:
                    month = str(int(month)).zfill(2)
                    if not (1 <= int(month) <= 12):
                        return jsonify({
                            'success': False,
                            'message': 'Неверный месяц. Допустимые значения: 1-12'
                        }), 400
                except ValueError:
                    return jsonify({
                        'success': False,
                        'message': 'Неверный формат месяца. Ожидается число'
                    }), 400
            else:
                month = datetime.now().strftime('%m')
            
            if year:
                try:
                    year = str(int(year))
                    if len(year) != 4:
                        return jsonify({
                            'success': False,
                            'message': 'Неверный формат года. Ожидается 4 цифры'
                        }), 400
                except ValueError:
                    return jsonify({
                        'success': False,
                        'message': 'Неверный формат года. Ожидается число'
                    }), 400
            else:
                year = datetime.now().strftime('%Y')
        
        logger.info(f"Запрос парсинга: source={source}, month={month}, year={year}")
        
        if source == 'news':
            parser = NewsParser()
            logger.info(f"Начало парсинга новостей за {month}.{year}")
            events = parser.parse(month=month, year=year)
            
            if not events:
                return jsonify({
                    'success': False,
                    'message': f'Не найдено новостей за {month}.{year}'
                }), 404
            
            saved, updated = parser.save_events(events)
            
            return jsonify({
                'success': True,
                'message': f'Успешно обработано {len(events)} новостей',
                'data': {
                    'total': len(events),
                    'saved': saved,
                    'updated': updated,
                    'month': month,
                    'year': year,
                    'source': 'news'
                }
            }), 200
            
        elif source == 'dod':
            parser = DodParser()
            logger.info("Начало парсинга дней открытых дверей")
            events = parser.parse()
            
            if not events:
                return jsonify({
                    'success': False,
                    'message': 'Не найдено дней открытых дверей'
                }), 404
            
            saved, updated = parser.save_events(events)
            
            return jsonify({
                'success': True,
                'message': f'Успешно обработано {len(events)} дней открытых дверей',
                'data': {
                    'total': len(events),
                    'saved': saved,
                    'updated': updated,
                    'source': 'dod'
                }
            }), 200
            
        elif source is None:
            results = []
            
            try:
                news_parser = NewsParser()
                news_events = news_parser.parse(month=month, year=year)
                if news_events:
                    saved, updated = news_parser.save_events(news_events)
                    results.append({
                        'source': 'news',
                        'total': len(news_events),
                        'saved': saved,
                        'updated': updated,
                        'month': month,
                        'year': year
                    })
            except Exception as e:
                logger.error(f"Ошибка парсинга новостей: {e}")
                results.append({
                    'source': 'news',
                    'error': str(e)
                })
            
            try:
                dod_parser = DodParser()
                dod_events = dod_parser.parse()
                if dod_events:
                    saved, updated = dod_parser.save_events(dod_events)
                    results.append({
                        'source': 'dod',
                        'total': len(dod_events),
                        'saved': saved,
                        'updated': updated
                    })
            except Exception as e:
                logger.error(f"Ошибка парсинга дней открытых дверей: {e}")
                results.append({
                    'source': 'dod',
                    'error': str(e)
                })
            
            return jsonify({
                'success': True,
                'message': f'Парсинг завершён для {len(results)} источников',
                'data': {
                    'results': results,
                    'month': month if month else None,
                    'year': year if year else None
                }
            }), 200
            
        else:
            return jsonify({
                'success': False,
                'message': f'Неизвестный источник: {source}. Доступные: news, dod'
            }), 400
            
    except Exception as e:
        logger.error(f"Ошибка в парсинге: {e}")
        return jsonify({
            'success': False,
            'message': f'Ошибка в парсинге: {str(e)}'
        }), 500
               
@api_bp.route('/events', methods=['GET'])
def get_events():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        if per_page > 100:
            per_page = 100
        if page < 1:
            page = 1

        query = Event.query

        event_type = request.args.get('event_type')
        if event_type:
            query = query.filter(Event.event_type == event_type)

        source_name = request.args.get('source_name')
        if source_name:
            query = query.filter(Event.source_name == source_name)

        is_active = request.args.get('is_active')
        if is_active is not None:
            if is_active.lower() == 'true':
                query = query.filter(Event.is_active == True)
            elif is_active.lower() == 'false':
                query = query.filter(Event.is_active == False)

        from_date = request.args.get('from_date')
        if from_date:
            try:
                date_obj = datetime.strptime(from_date, '%Y-%m-%d')
                query = query.filter(Event.event_date >= date_obj)
            except ValueError:
                return jsonify({'error': 'Неверный формат from_date. Ожидается YYYY-MM-DD'}), 400

        to_date = request.args.get('to_date')
        if to_date:
            try:
                date_obj = datetime.strptime(to_date, '%Y-%m-%d')
                query = query.filter(Event.event_date <= date_obj)
            except ValueError:
                return jsonify({'error': 'Неверный формат to_date. Ожидается YYYY-MM-DD'}), 400

        query = query.order_by(Event.event_date.desc(), Event.id.desc())

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        events = [event.to_dict() for event in paginated.items]

        return jsonify({
            'items': events,
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'pages': paginated.pages,
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next
        }), 200

    except Exception as e:
        logger.error(f"Ошибка в GET /api/events: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/events/<int:id>', methods=['GET'])
def get_event(id):
    try:
        event = Event.query.get(id)
        if not event:
            return jsonify({'error': 'Событие не найдено'}), 404
        return jsonify(event.to_dict()), 200
    except Exception as e:
        logger.error(f"Ошибка в GET /api/events/{id}: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/events/upcoming', methods=['GET'])
def get_upcoming_events():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        if per_page > 100:
            per_page = 100
        if page < 1:
            page = 1

        now = datetime.now(timezone.utc)
        query = Event.query.filter(
            #Event.event_date >= now,
            Event.is_active == True
        ).order_by(Event.event_date.asc())

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        events = [event.to_dict() for event in paginated.items]

        return jsonify({
            'items': events,
            'total': paginated.total,
            'page': page,
            'per_page': per_page,
            'pages': paginated.pages,
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next
        }), 200

    except Exception as e:
        logger.error(f"Ошибка в GET /api/events/upcoming: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    try:
        total = Event.query.count()
        active = Event.query.filter_by(is_active=True).count()
        inactive = total - active

        sources_count = db.session.query(func.count(distinct(Event.source_name))).scalar() or 0

        last_parsed = db.session.query(func.max(Event.parsed_at)).scalar()
        last_parsed_at = last_parsed.isoformat() if last_parsed else None

        source_stats = db.session.query(
            Event.source_name,
            func.count(Event.id).label('count')
        ).group_by(Event.source_name).all()
        sources = {s.source_name: s.count for s in source_stats if s.source_name}

        type_stats = db.session.query(
            Event.event_type,
            func.count(Event.id).label('count')
        ).group_by(Event.event_type).all()
        types = {t.event_type: t.count for t in type_stats if t.event_type}

        now = datetime.now(timezone.utc)
        upcoming = Event.query.filter(Event.event_date >= now, Event.is_active == True).count()

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        added_last_week = Event.query.filter(Event.created_at >= week_ago).count()

        return jsonify({
            'total_events': total,
            'sources_count': sources_count,
            'last_parsed_at': last_parsed_at,
            'error_count': 0, 

            'active': active,
            'inactive': inactive,
            'upcoming': upcoming,
            'added_last_7_days': added_last_week,
            'by_source': sources,
            'by_type': types
        }), 200

    except Exception as e:
        logger.error(f"Ошибка в GET /api/stats: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/export', methods=['GET'])
def export_events():
    try:
        query = Event.query

        event_type = request.args.get('event_type')
        if event_type:
            query = query.filter(Event.event_type == event_type)

        source_name = request.args.get('source_name')
        if source_name:
            query = query.filter(Event.source_name == source_name)

        is_active = request.args.get('is_active')
        if is_active is not None:
            if is_active.lower() == 'true':
                query = query.filter(Event.is_active == True)
            elif is_active.lower() == 'false':
                query = query.filter(Event.is_active == False)

        from_date = request.args.get('from_date')
        if from_date:
            try:
                date_obj = datetime.strptime(from_date, '%Y-%m-%d')
                query = query.filter(Event.event_date >= date_obj)
            except ValueError:
                return jsonify({'error': 'Неверный формат from_date. Ожидается YYYY-MM-DD'}), 400

        to_date = request.args.get('to_date')
        if to_date:
            try:
                date_obj = datetime.strptime(to_date, '%Y-%m-%d')
                query = query.filter(Event.event_date <= date_obj)
            except ValueError:
                return jsonify({'error': 'Неверный формат to_date. Ожидается YYYY-MM-DD'}), 400

        events = query.order_by(Event.event_date.desc()).all()
        data = [event.to_dict() for event in events]

        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        buffer = io.BytesIO(json_str.encode('utf-8'))
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'events_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )

    except Exception as e:
        logger.error(f"Ошибка в GET /api/export: {e}")
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500


@api_bp.route('/import', methods=['POST'])
def import_events():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Тело запроса должно содержать JSON-массив'}), 400

        if not isinstance(data, list):
            return jsonify({'error': 'Ожидается массив объектов'}), 400

        created = 0
        updated = 0
        errors = []

        for idx, item in enumerate(data):
            external_id = item.get('external_id')
            if not external_id:
                errors.append({'index': idx, 'error': 'Отсутствует external_id'})
                continue

            event = Event.query.filter_by(external_id=external_id).first()

            try:
                if event:
                    event.title = item.get('title', event.title)
                    event.description = item.get('description', event.description)
                    date_str = item.get('event_date')
                    if date_str:
                        try:
                            if isinstance(date_str, str):
                                if date_str.endswith('Z'):
                                    date_str = date_str[:-1] + '+00:00'
                                event.event_date = datetime.fromisoformat(date_str)
                            else:
                                event.event_date = date_str
                        except (ValueError, TypeError):
                            errors.append({'index': idx, 'external_id': external_id, 'error': 'Неверный формат event_date'})
                            continue
                    event.location = item.get('location', event.location)
                    event.event_type = item.get('event_type', event.event_type)
                    event.source_url = item.get('source_url', event.source_url)
                    event.source_name = item.get('source_name', event.source_name)
                    if 'is_active' in item:
                        event.is_active = bool(item['is_active'])
                    event.updated_at = datetime.now(timezone.utc)
                    updated += 1
                else:
                    new_event = Event(
                        external_id=external_id,
                        title=item.get('title', ''),
                        description=item.get('description'),
                        location=item.get('location'),
                        event_type=item.get('event_type'),
                        source_url=item.get('source_url'),
                        source_name=item.get('source_name'),
                        is_active=item.get('is_active', True),
                    )
                    date_str = item.get('event_date')
                    if date_str:
                        try:
                            if isinstance(date_str, str):
                                if date_str.endswith('Z'):
                                    date_str = date_str[:-1] + '+00:00'
                                new_event.event_date = datetime.fromisoformat(date_str)
                            else:
                                new_event.event_date = date_str
                        except (ValueError, TypeError):
                            errors.append({'index': idx, 'external_id': external_id, 'error': 'Неверный формат event_date'})
                            continue
                    db.session.add(new_event)
                    created += 1

            except Exception as e:
                errors.append({'index': idx, 'external_id': external_id, 'error': str(e)})
                continue

        db.session.commit()

        imported = created + updated
        skipped = len(errors)

        return jsonify({
            'success': True,
            'imported': imported,
            'skipped': skipped,
            'created': created,
            'updated': updated,
            'errors': errors
        }), 200 if not errors else 207

    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка в POST /api/import: {e}")
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500