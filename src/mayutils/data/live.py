from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
from pandas import DataFrame

from mayutils.data.read import QUERIES_FOLDERS, get_query_data


class LiveData(object):
    """
    Class to manage live data updates and aggregation.

    Assumptions:
        - Data is pulled via a named SQL query in an appropriate queries folder
        - This SQL query has a timestamp column to index time against
        - This SQL query can be formatted with `start_timestamp` and `end_timestamp` to select incremental data
        - Data is stored in a pandas DataFrame
    """

    def __init__(
        self,
        query_name: str,
        index_column: str,
        start_timestamp: datetime,
        rolling: bool = True,
        aggregation: Callable[[DataFrame], DataFrame] = lambda df: df,
        queries_folders: tuple[Path, ...] = QUERIES_FOLDERS,
        update_frequency: Optional[timedelta] = None,
        **query_kwargs,
    ) -> None:
        # TODO: Second tier updates for stuff up to yesterday from old db and stuff from yday being from redash - timepoint cutoff for most recent pull
        self.time_format = "%Y-%m-%d %H:%M:%S"
        self.query_name = query_name
        self.queries_folders = queries_folders
        self.index_column = index_column
        self.query_kwargs = query_kwargs
        self.time_columns = tuple(
            set(self.query_kwargs.pop("time_columns", tuple()) + (index_column,))
        )

        self.rolling = rolling
        self.aggregation = aggregation

        self.initialisation_timestamp = datetime.now()

        self.period = (start_timestamp, self.initialisation_timestamp)
        self.interval = self.period[1] - self.period[0]
        self.update_frequency = update_frequency

        self.data = get_query_data(
            query_name=self.query_name,
            queries_folders=self.queries_folders,
            cache=True,
            start_timestamp=self.period[0].strftime(format=self.time_format),
            end_timestamp=self.period[1].strftime(format=self.time_format),
            time_columns=self.time_columns,
            **self.query_kwargs,
        )

        self._get_aggregated_data()

        return None

    def update(
        self,
        force: bool = False,
    ) -> "LiveData":
        current_timestamp = datetime.now()
        if (
            force
            or self.update_frequency is None
            or ((current_timestamp - self.period[1]) > self.update_frequency)
        ):
            new_period = (
                current_timestamp - self.interval if self.rolling else self.period[0],
                current_timestamp,
            )

            if self.rolling:
                # elapsed_period = (previous_period[0], self.period[0])
                self.data = self.data.loc[
                    self.data[self.index_column] >= new_period[0]
                ]

            # new_period = (previous_period[1], self.period[1])»
            additional_data = get_query_data(
                query_name=self.query_name,
                queries_folders=self.queries_folders,
                cache=True,
                start_timestamp=self.period[1].strftime(format=self.time_format),
                end_timestamp=new_period[1].strftime(format=self.time_format),
                time_columns=self.time_columns,
                **self.query_kwargs,
            )
            self.data = pd.concat([self.data, additional_data])

            self._get_aggregated_data()

            self.period = new_period

        return self

    def _get_aggregated_data(
        self,
    ) -> DataFrame:
        self.aggregated_data = self.aggregation(self.data)

        return self.aggregated_data

    def reset(
        self,
        start_timestamp: Optional[datetime] = None,
    ) -> "LiveData":
        self.__init__(
            query_name=self.query_name,
            index_column=self.index_column,
            start_timestamp=start_timestamp or self.period[0],
            rolling=self.rolling,
            aggregation=self.aggregation,
            queries_folders=self.queries_folders,
            update_frequency=self.update_frequency,
            **self.query_kwargs,
        )

        return self
