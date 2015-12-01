"""All database operations are abstracted here."""

import os, time

import sqlalchemy
from sqlalchemy.exc import IntegrityError

db_uri = os.environ['DATABASE_URL']  # must be set, e.g. 'postgres:///local'
db = None  # open_db() must be called before anything else

def open_db():
    global db
    db = sqlalchemy.create_engine(db_uri)

def close_db():
    global db
    db.dispose()
    db = None

def get_all_links():
    return db.execute('select name, url, count from urls order by name')

def get_url(name):
    row = db.execute('select url from urls where name = %s', name).first()
    return row and row[0]

def update_link(name, new_name, new_url):
    return db.execute('update urls set name = %s, url = %s '
                      'where name = %s', new_name, new_url, name).rowcount > 0

def add_link(name, url):
    db.execute('insert into urls (name, url) values (%s, %s)', name, url)

def update_count(name):
    (count,) = db.execute('select count(*) from events where '
                          'event = %s and name = %s', 'redirect', name).first()
    db.execute('update urls set count = %s where name = %s', count, name)

def log(event, name, url):
    db.execute('insert into events (time, event, name, url) '
               'values (%s, %s, %s, %s)',
               int(time.time()*1000), event, name, url)

def reset_app():
    """Not called by the app.  Call this to set up a fresh database."""
    open_db()
    db.execute('''
drop table if exists urls;

create table urls (
    name varchar(100) primary key,
    url varchar(10000),
    count bigint default 0
);

create index on urls (count);
create index on urls (url);

drop table if exists events;

create table events (
    time bigint,
    event varchar(100),
    name varchar(100),
    url varchar(10000)
);

create index on events (event, name);
''')
