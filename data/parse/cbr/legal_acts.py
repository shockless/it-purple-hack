import argparse
import csv
import dataclasses
from collections.abc import Iterator
from functools import cached_property
from typing import Any

import bs4
from progress.bar import Bar

from data.parse.cbr.base import BaseCBRParser, Document


class LegalActsParser(BaseCBRParser):
    @cached_property
    def _initial_page(self) -> bs4.BeautifulSoup:
        r = self.request(self.get_full_url('na'))

        return bs4.BeautifulSoup(r.content, 'html.parser')

    @property
    def page_base_url(self) -> str:
        next_button = self._initial_page.select_one('#la_load')
        return next_button['data-cross-ajax-url'].split('?', 1)[0]

    @property
    def page_size(self) -> int:
        return len(self._initial_page.select('#content > div > div > div > div.cross-results > div.cross-result'))

    @property
    def total_items(self) -> int:
        text = self.extract_text(self._initial_page.select_one('div.results div.results_counter'))
        return int(text.split(' ', 1)[0]) - self._start_from_idx

    @property
    def total_pages(self) -> int:
        return (self.total_items + self.page_size - 1) // self.page_size

    @property
    def _start_page_idx(self) -> int:
        return self._start_from_idx // self.page_size

    @staticmethod
    def _get_params_for_page(page_idx: int) -> dict[str, Any]:
        return {
            'Date.Time': 'Any',
            'Page': page_idx,
        }

    def proceed_page(self, page_idx: int) -> Iterator[Document]:
        r = self.request(self.get_full_url(self.page_base_url), params=self._get_params_for_page(page_idx))

        soup = bs4.BeautifulSoup(r.content, 'html.parser')
        results_list = soup.select('div.cross-result')
        if self._start_page_idx == page_idx:
            results_list = results_list[self._start_from_idx % self.page_size:]

        for cross_result in results_list:
            yield self.proceed_item(cross_result)

    def proceed_item(self, tag: bs4.Tag) -> Document:
        title = tag.select_one('div.title-source > div.title a')
        url = title['href']
        try:
            text = self.fetch_document_text(url)
        except:  # noqa
            text = None
        doc = Document(url=url, text=text)
        self._progress_bar.next()
        return doc

    def proceed(self) -> Iterator[Document]:
        for page_idx in range(self._start_page_idx, self._start_page_idx + self.total_pages):
            yield from self.proceed_page(page_idx)
        self._progress_bar.finish()


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--start-from-idx', type=int, default=0)
    args = arg_parser.parse_args()

    parser = LegalActsParser(Bar, args.start_from_idx)
    with open('legal_acts.csv', 'a') as fd:
        writer = csv.writer(fd)
        for doc in parser.proceed():
            writer.writerow(dataclasses.astuple(doc))


if __name__ == '__main__':
    main()
