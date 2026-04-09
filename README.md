# lab_grants-db

Приложение на Python и PyQt6 для ведения базы грантов и конкурсов.

Функции:
- просмотр грантов в графическом интерфейсе;
- поиск и фильтрация по статусу и организатору;
- добавление в избранное;
- экспорт в Excel;
- загрузка конкурсов РНФ с сайта `rscf.ru`.

## Требования

- Python 3.10+
- `pip`

## Установка и запуск

### Linux

Подходит для CachyOS, Arch Linux, Ubuntu и других дистрибутивов.

Создайте и активируйте виртуальное окружение:

```bash
python -m venv .venv
source .venv/bin/activate
```

Установите зависимости и запустите программу:

```bash
pip install -r requirements.txt
python main.py
```

### Windows

Откройте `PowerShell` или `cmd` в папке проекта.

Для `PowerShell`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Для `cmd`:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python main.py
```

При первом запуске рядом с программой будет создан файл базы данных `grants.db`.

## Вход в приложение

Тестовые учетные записи:

- `admin / admin123`
- `user / user123`

Права:
- `admin` может добавлять, редактировать, удалять записи и запускать парсер РНФ;
- `user` может просматривать базу и работать с избранным.

## Файлы проекта

- `main.py` - графический интерфейс, работа с SQLite и экспорт в Excel;
- `parser_rnf.py` - парсер конкурсов РНФ;
- `requirements.txt` - зависимости проекта.

## Примечание

Для загрузки данных РНФ требуется доступ в интернет, так как приложение получает информацию с сайта `https://rscf.ru/contests/`.
