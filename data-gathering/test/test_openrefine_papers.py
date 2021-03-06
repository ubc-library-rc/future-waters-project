from __future__ import print_function

import csv
import json
import logging
import os
import sys
import datetime

# adding path to run files from root when in docker container
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from colorama import Fore, Style

from futurewater.keywords import get_publication_subject
from futurewater.util import format_author, to_quickstatements_format

# https://stackoverflow.com/questions/11029717/how-do-i-disable-log-messages-from-the-requests-library
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger()
logger.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)


def wikidata_import(author_name, open_refine, test=False):
    # if author_name not in ['Alice Guimaraes', 'Annegaaike Leopold']:
    #     logger.error(Fore.RED + f' {author_name} ' + Style.RESET_ALL + 'skipped for debugging')
    #     return
    resources_folder = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "..", "resources"
    )
    author_file = format_author(author_name)
    output_folder = os.path.join(resources_folder, "wikidata")
    cached = os.path.join(output_folder, author_file)

    result = []
    if os.path.isfile(cached):
        with open(cached) as fo:
            data = json.load(fo)

            if data['author'] in open_refine and open_refine[data['author']] != "":
                author = open_refine[data['author']]
            elif data['wikidata_id']:
                author = data['wikidata_id']
            else:
                author = data['author']  # author

            for row in data['missing_data']:
                try:
                    title = None
                    if row['title']:
                        title = next(iter(row['title']))
                    if not title and 'original_title' in row:
                        title = row['original_title']

                    if not title:
                        continue

                    main_subject = get_publication_subject(author_name, row, title=title)  # main subject,
                    published_in=None
                    if 'container-title' in row:
                        published_in = next(iter(row['container-title']))
                    elif 'publisher' in row:
                        published_in = row['publisher']
                    created = None
                    if 'created' in row and 'date-time' in row['created']:
                        created = row['created']['date-time'].split('T')[0]

                    # Dictionary sorted by properties
                    new_entry = dict(
                        Len=to_quickstatements_format(title),
                        P31='Q13442814',  # instance of = scholarly article,
                        P50=author,  # author
                        P356=row['DOI'],  # DOI
                        P921=main_subject,  # main subject,
                        P1476=to_quickstatements_format(title),  # title
                        P1433=to_quickstatements_format(published_in),  # published in
                        P577=created  # publication date
                    )
                    result.append(new_entry)
                except Exception as ex:
                    logger.exception(ex)

    return result


def write_output_file(data, author, individual_files=True):
    if not data:
        return
    keys = data[0].keys()
    file_name = '_'.join(author.split()).lower().replace('.', '')
    _output = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           '..', 'resources', 'papers')

    _output = os.path.join(_output, f'paper_data_{file_name}.json')

    with open(_output, "w") as outfile:
        json.dump(data, outfile, indent=4)

    # Removes main subject from jsons because it is not used in Open Refine
    for d in data:
        d.pop("P921", None)  # https://stackoverflow.com/questions/15411107/delete-a-dictionary-item-if-the-key-exists

    _output = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                           '..', 'resources', 'imports')
    if individual_files:
        _output = os.path.join(_output, 'authors')

    _output = os.path.join(_output, f'open_refine_{file_name}.csv')
    with open(_output, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys, quoting=csv.QUOTE_ALL)
        dict_writer.writeheader()
        dict_writer.writerows(data)


def main():
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    _input = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '..', 'resources', 'cluster-members.csv'
    )

    authors = []
    with open(_input) as _f:
        _data = csv.DictReader(_f)
        for row in _data:
            authors.append(row['Full Name'])

    final_data = []
    idx = 0
    for author_name in authors:
        try:
            openrefine_import = wikidata_import(author_name, dict())
            if openrefine_import:
                final_data += openrefine_import
                write_output_file(
                    sorted(openrefine_import, key=lambda k: k['P1476']),
                    author_name
                )
        except Exception as ex:
            logger.exception(ex)


    write_output_file(
        sorted(final_data, key=lambda k: k['P1476']),
        'full_paper_list',
        individual_files=False
    )


if __name__ == '__main__':
    logger.info("\n\nWriting wikidata for every" + Fore.YELLOW + " paper " + Style.RESET_ALL + " in the cluster")
    main()
    logger.info(">> " + Fore.YELLOW + "Open Refine" + Style.RESET_ALL + " output at " + Fore.RED + "./resources/imports/authors" + Style.RESET_ALL)
    logger.info(">> " + Fore.YELLOW + "Scholia" + Style.RESET_ALL + " output at " + Fore.RED + "./resources/papers" + Style.RESET_ALL)
    logger.info('-' * 10)
    logger.info('-' * 10)
