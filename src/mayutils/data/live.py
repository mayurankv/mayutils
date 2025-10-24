from typing import Callable, Optional, Self
from pandas import DataFrame
import pandas as pd
from mayutils.objects.datetime import DateTime, Interval, Duration
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

    def _initialise(
        self,
        query_string: str,
        engine: EngineWrapper,
        index_column: str,
        start_timestamp: DateTime,
        rolling: bool = True,
        aggregations: dict[str, Callable[[DataFrame], DataFrame]] = {},
        update_frequency: Optional[Duration] = None,
        time_format: str = "%Y-%m-%d",
        **format_kwargs,
    ) -> None:
        # TODO: Second tier updates for stuff up to yesterday from old db and stuff from yday being from redash - timepoint cutoff for most recent pull
        self.time_format = time_format

        self.query_string = query_string
        self.engine = engine
        self.index_column = index_column
        self.format_kwargs = format_kwargs

        self.rolling = rolling
        self.aggregations = aggregations

        self.initialisation_timestamp = DateTime.now()

        self.interval = Interval(
            start=start_timestamp,
            end=self.initialisation_timestamp,
            absolute=True,
        )
        self.update_frequency = update_frequency

        self.data = self.engine.read_pandas(
            query_string=self.query_string.format(
                start_timestamp=self.interval.start.strftime(format=self.time_format),
                end_timestamp=self.interval.end.strftime(format=self.time_format),
                **self.format_kwargs,
            )
        )

        self.empty = self.data.empty
        if not self.empty:
            self._get_aggregated_data()

        return None

    def __init__(
        self,
        query_string: str,
        engine: EngineWrapper,
        index_column: str,
        start_timestamp: DateTime,
        rolling: bool = True,
        aggregations: dict[str, Callable[[DataFrame], DataFrame]] = {},
        update_frequency: Optional[Duration] = None,
        time_format: str = "%Y-%m-%d",
        **format_kwargs,
    ) -> None:
        return self._initialise(
            query_string=query_string,
            engine=engine,
            index_column=index_column,
            start_timestamp=start_timestamp,
            rolling=rolling,
            aggregations=aggregations,
            update_frequency=update_frequency,
            time_format=time_format,
            **format_kwargs,
        )

    def _update(
        self,
        now: DateTime,
        engine: EngineWrapper,
    ) -> None:
        new_interval = Interval(
            start=(now - self.interval.as_duration())
            if self.rolling
            else self.interval.start,
            end=now,
        )

        if self.rolling:
            # elapsed_period = (previous_period[0], self.period[0])
            self.data = self.data.loc[
                self.data[self.index_column] >= new_interval.start.naive()
            ]

        # new_period = (previous_period[1], self.period[1])»
        additional_data = engine.read_pandas(
            query_string=self.query_string.format(
                start_timestamp=self.interval.end.strftime(format=self.time_format),
                end_timestamp=new_interval.end.strftime(format=self.time_format),
                **self.format_kwargs,
            )
        )

        if not additional_data.empty:
            if not self.empty:
                self.data = pd.concat([self.data, additional_data])

            else:
                self.data = additional_data

            self._get_aggregated_data()

            self.interval = new_interval

        return

    def update(
        self,
        engine: Optional[EngineWrapper] = None,
        force: bool = False,
    ) -> Self:
        now = DateTime.now()

        if engine is None:
            engine = self.engine

        if (
            force
            or self.update_frequency is None
            or ((now - self.interval.end) > self.update_frequency)
        ):
            self._update(
                now=now,
                engine=engine,
            )

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
        start_timestamp: Optional[DateTime] = None,
    ) -> Self:
        self._initialise(
            query_string=self.query_string,
            engine=self.engine,
            index_column=self.index_column,
            start_timestamp=start_timestamp or self.interval.start,
            rolling=self.rolling,
            aggregations=self.aggregations,
            update_frequency=self.update_frequency,
            **self.format_kwargs,
        )

        return self
