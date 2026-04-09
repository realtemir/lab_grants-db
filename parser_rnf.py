import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from datetime import datetime


RNF_STATUSES = ("Все", "Прием заявок", "Экспертиза", "Завершенные")
RNF_ACTIVE_STATUS_SELECTOR = "span.contest-success, span.text-warning, span.contest-danger"


def _norm_text(value: str) -> str:
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = value.replace("ё", "е")
    value = re.sub(r"\s+", " ", value)
    return value


def _canonical_target_status(target_status: str) -> str:
    """
    Приводит входной фильтр статуса к одному из:
    - "Все"
    - "Прием заявок"
    - "Экспертиза"
    - "Завершенные"
    """
    ts = _norm_text(target_status)
    if not ts or "все" in ts or "любой" in ts:
        return "Все"

    if "прием" in ts or "прием заявок" in ts:
        return "Прием заявок"
    if "экспертиз" in ts:
        return "Экспертиза"

    # Сюда попадают "подведение итогов", "завершён", "завершенные" и т.п.
    if "итог" in ts or "заверш" in ts or "результ" in ts:
        return "Завершенные"

    # На всякий случай: неизвестные значения не ломают парсинг
    return "Все"


def _canonical_contest_status(raw_status_text: str) -> str:
    """
    Приводит статус с сайта РНФ к одному из значений RNF_STATUSES (кроме "Все").
    """
    s = _norm_text(raw_status_text)

    if "прием" in s or "прием заявок" in s:
        return "Прием заявок"
    if "экспертиз" in s:
        return "Экспертиза"

    # На сайте встречается "Конкурс завершён"/"Подведение итогов" и т.п. — считаем завершенными
    if "заверш" in s or "итог" in s or "результ" in s:
        return "Завершенные"

    # Остальные/неожиданные статусы безопаснее отнести к завершенным
    return "Завершенные"

def analyze_rnf_details(title):
    title_lower = title.lower()
    target = "Научные коллективы"
    if "малых отдельных" in title_lower:
        target = "Малые научные группы (2-4 чел.)"
    elif "молодых ученых" in title_lower or "молодежных" in title_lower:
        target = "Молодые ученые"
    elif "лабораторий" in title_lower:
        target = "Научные лаборатории"
    elif "международн" in title_lower:
        target = "Международные коллективы"
        
    max_amount = "Согласно конкурсной документации"
    if "малых" in title_lower:
        max_amount = "до 1.5 млн руб. в год"
    elif "отдельных научных групп" in title_lower:
        max_amount = "до 7 млн руб. в год"
    elif "молодежных" in title_lower and "президентск" in title_lower:
        max_amount = "до 6 млн руб. в год"
    elif "лабораторий" in title_lower:
        max_amount = "до 30 млн руб. в год"
    elif "передовых" in title_lower or "технологий" in title_lower:
        max_amount = "от 10 до 30 млн руб."
        
    description = (f"Конкурс проводится по направлению: {target}. "
                   f"Ориентировочное финансирование: {max_amount}. "
                   "Для точных данных перейдите по ссылке.")
                   
    return max_amount, target, description

def parse_rnf_grants(target_status="Все", date_start=None, date_end=None):
    """
    Продвинутый парсер РНФ.
    Переходит по страницам (PAGEN_2) и отсеивает конкурсы по статусу и КАЛЕНДАРНЫМ ДАТАМ.
    """
    base_url = "https://rscf.ru/contests/"
    headers = {"User-Agent": "Mozilla/5.0"}
    grants = []
    
    target_status = _canonical_target_status(target_status)

    status_param_map = {
        "Прием заявок": "acceptance",
        "Экспертиза": "review",
        "Завершенные": "finished",
    }

    # Для конкретного фильтра используем соответствующую вкладку сайта.
    # Для "Все" оставляем базовую страницу без status-параметра.
    status_params = [None] if target_status == "Все" else [status_param_map[target_status]]

    max_pages = 25

    for status_param in status_params:
        page = 1
        while page <= max_pages:
            params = {}
            if status_param:
                params["status"] = status_param
            if page > 1:
                params["PAGEN_2"] = page

            if params:
                url = base_url + "?" + urllib.parse.urlencode(params)
            else:
                url = base_url

            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print(f"Ошибка загрузки страницы {page}: {e}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.find_all(class_='contest-table-row')
            if not rows:
                break

            for row in rows:
                name_elem = row.find(class_='contest-name')
                if not name_elem:
                    continue
                title = name_elem.get_text(strip=True)

                status_elem = row.find(class_='contest-status')
                status_text = ""
                if status_elem:
                    # Активный этап подсвечивается одним из классов:
                    # - "contest-success" (Прием заявок)
                    # - "text-warning" (Экспертиза)
                    # - "contest-danger" (Конкурс завершен)
                    active_span = status_elem.select_one(RNF_ACTIVE_STATUS_SELECTOR)
                    if active_span:
                        status_text = active_span.get_text(strip=True)
                    else:
                        status_text = status_elem.get_text(" ", strip=True)

                status_db = _canonical_contest_status(status_text)
                if target_status != "Все" and status_db != target_status:
                    continue

                date_elem = row.find(class_='contest-date')
                deadline_str = date_elem.get_text(strip=True).replace("до", "").strip() if date_elem else ""

                # --- ВНЕДРЕНИЕ КАЛЕНДАРНОГО ФИЛЬТРА ---
                if date_start or date_end:
                    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', deadline_str)
                    if match:
                        grant_date = datetime(int(match.group(3)), int(match.group(2)), int(match.group(1))).date()

                        if date_start and grant_date < date_start:
                            continue
                        if date_end and grant_date > date_end:
                            continue

                link_elem = row.find('a', class_='contest-link')
                link = urllib.parse.urljoin(url, link_elem.get('href')) if link_elem and link_elem.get('href') else url

                max_amt, target_group, desc = analyze_rnf_details(title)

                if not any(g['title'] == title for g in grants):
                    grants.append({
                        'title': title,
                        'organizer': 'РНФ',
                        'max_amount': max_amt,
                        'deadline': deadline_str,
                        'target': target_group,
                        'description': desc,
                        'requirements': 'Наличие публикаций WOS/Scopus (см. документацию).',
                        'url': link,
                        'status': status_db
                    })

            page += 1
        
    return grants
