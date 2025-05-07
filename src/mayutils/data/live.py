from datetime import datetime, timedelta
from typing import Callable, Optional, Self

import pandas as pd
from pandas import DataFrame

from mayutils.environment.databases import EngineWrapper


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
        query_string: str,
        engine: EngineWrapper,
        index_column: str,
        start_timestamp: datetime,
        rolling: bool = True,
        aggregations: dict[str, Callable[[DataFrame], DataFrame]] = {},
        update_frequency: Optional[timedelta] = None,
        **format_kwargs,
    ) -> None:
        # TODO: Second tier updates for stuff up to yesterday from old db and stuff from yday being from redash - timepoint cutoff for most recent pull
        self.time_format = "%Y-%m-%d"

        self.query_string = query_string
        self.engine = engine
        self.index_column = index_column
        self.format_kwargs = format_kwargs

        self.rolling = rolling
        self.aggregations = aggregations

        self.initialisation_timestamp = datetime.now()

        self.period = (start_timestamp, self.initialisation_timestamp)
        self.interval = self.period[1] - self.period[0]
        self.update_frequency = update_frequency

        self.data = self.engine.read_pandas(
            query_string=self.query_string.format(
                start_timestamp=self.period[0].strftime(format=self.time_format),
                end_timestamp=self.period[1].strftime(format=self.time_format),
                **self.format_kwargs,
            )
        )

        self._get_aggregated_data()

        return None

    def update(
        self,
        engine: Optional[EngineWrapper] = None,
        force: bool = False,
    ) -> "LiveData":
        current_timestamp = datetime.now()
        if engine is None:
            engine = self.engine
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
                self.data = self.data.loc[self.data[self.index_column] >= new_period[0]]

            # new_period = (previous_period[1], self.period[1])»
            additional_data = self.engine.read_pandas(
                query_string=self.query_string.format(
                    start_timestamp=self.period[1].strftime(format=self.time_format),
                    end_timestamp=new_period[1].strftime(format=self.time_format),
                    **self.format_kwargs,
                )
            )
            self.data = pd.concat([self.data, additional_data])

            self._get_aggregated_data()

            self.period = new_period

        return self

    def _get_aggregated_data(
        self,
    ) -> dict[str, DataFrame]:
        self.aggregated_data = {
            aggregation_name: aggregation(self.data)
            for aggregation_name, aggregation in self.aggregations.items()
        }

        return self.aggregated_data

    def reset(
        self,
        start_timestamp: Optional[datetime] = None,
    ) -> Self:
        self.__init__(
            query_string=self.query_string,
            engine=self.engine,
            index_column=self.index_column,
            start_timestamp=start_timestamp or self.period[0],
            rolling=self.rolling,
            aggregations=self.aggregations,
            update_frequency=self.update_frequency,
            **self.format_kwargs,
        )

        return self
