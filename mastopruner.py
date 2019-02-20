#!/usr/bin/env python2
import ConfigParser
import datetime
import dateutil
import getpass
import time

CONFIG_FILE = None
MAX_COUNT = 1
DEBUG = False


def read_app_credentials(filename="app_credentials.cfg"):
    creds = ConfigParser.RawConfigParser()
    creds.read(filename)
    return creds


def read_config_file(filename=None):
    """Read and parse the configuration file, returning it as a ConfigParser
       object."""
    global CONFIG_FILE

    config = ConfigParser.RawConfigParser()

    if filename is None:
        filename = CONFIG_FILE

    config.read(filename)
    CONFIG_FILE = filename

    return config


def write_config_file(config):
    """Writes the configuration object to the previously-read config file."""
    global CONFIG_FILE

    if CONFIG_FILE is None:
        raise RuntimeError('CONFIG_FILE is None')

    with open(CONFIG_FILE, 'w') as fp:
        config.write(fp)


def get_mastodon(credentials, config):
    """Returns a Mastodon connection object."""
    from mastodon import Mastodon

    if not credentials.has_section('mastodon'):
        raise RuntimeError("no [mastodon] section in app credentials")

    for key in ['client_key', 'client_secret', 'instance']:
        if not credentials.has_option('mastodon', key):
            raise RuntimeError("no %s key in app credentials" % key)

    if not config.has_section('mastodon'):
        config.add_section('mastodon')
        write_config_file(config)

    # Log in
    if not config.has_option('mastodon', 'access_token'):
        mastodon = Mastodon(
                    ratelimit_method='pace',
                    client_id=credentials.get('mastodon', 'client_key'),
                    client_secret=credentials.get('mastodon', 'client_secret'),
                    api_base_url=credentials.get('mastodon', 'instance'))
        print("Logging into %s..." % credentials.get('mastodon', 'instance'))
        username = raw_input('E-mail address: ')
        password = getpass.getpass('Password: ')
        access_token = mastodon.log_in(username, password)
        config.set('mastodon', 'access_token', access_token)
        write_config_file(config)

    return Mastodon(
            client_id=credentials.get('mastodon', 'client_key'),
            client_secret=credentials.get('mastodon', 'client_secret'),
            api_base_url=credentials.get('mastodon', 'instance'),
            access_token=config.get('mastodon', 'access_token'))


def status_iter(m, limit=20, min_days=0, tags=[], include_favorites=True,
                include_public=True):
    me = m.account_verify_credentials()
    max_id = None
    min_td = datetime.timedelta(days=min_days)
    tags = [t.lower() for t in tags]

    while limit > 0:
        #print("Fetching block (max_id %d, remaining %d)" % (max_id or -1, limit))
        statuses = m.account_statuses(me, max_id=max_id, limit=40)

        if len(statuses) == 0:
            break

        for s in statuses:
            candidate = False

            if max_id is None or max_id > s.id:
                max_id = s.id

            td = datetime.datetime.now(tz=dateutil.tz.tzutc()) - s.created_at
            print("Considering: %d (%s) pinned=%s td=%s vs %s" % (s.id, s.created_at, None, td, min_td))

            candidate = td > min_td
            candidate = candidate and (include_favorites or (s.favourites_count == 0 and s.reblogs_count == 0))
            #candidate = candidate and not s.pinned

            if candidate and len(tags) > 0:
                tag_found = False
                for t in s.tags:
                    tag_found = tag_found or t.name.lower() in tags

            if candidate:
                yield s
                limit -= 1

            if limit <= 0:
                break


def cleanup_old(m, min_days=30, tags=[]):
    for s in status_iter(m, min_days=min_days, tags=tags, include_favorites=True, limit=20000):
        print("Deleting status: %d" % s.id)
        m.status_delete(s)


def main():
    creds = read_app_credentials()
    cfg = read_config_file('config.cfg')

    masto = get_mastodon(creds, cfg)

    cleanup_old(masto, min_days=90)


main()

