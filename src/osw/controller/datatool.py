from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import PrivateAttr, validator

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.controller.database import DatabaseController, TimescaleDbController
from osw.core import OSW
from osw.model.static import OswBaseModel


class DataToolController(model.IndividualDevice):
    """
    Provides functionalities for DataTool instances
    """

    osw: Optional[OSW]
    """ an OSW instance to fetch related resources (host, server, etc.)"""
    cm: Optional[CredentialManager]
    """ CredentialManager to login to the database"""

    _device_type: Optional[model.DataDevice] = PrivateAttr()

    _data_base: Optional[TimescaleDbController] = PrivateAttr()

    _data_schemas: Optional[Dict[str, model.Dataset]] = PrivateAttr()
    # _data: List[Dict[DataSource]]

    class ConnectionConfig(OswBaseModel):
        """Database connection configuration"""

        osw: OSW
        """ OSW instance to fetch related resources (host, server, etc.) """
        cm: Union[CredentialManager.Credential, CredentialManager]
        """ CredentialManager or direct Credential to login to the database"""

    def connect(self, config: ConnectionConfig):
        """Initializes the connection to the database by creating a sqlalchemy engine

        Parameters
        ----------
        config
            see ConnectionConfig
        """
        self.osw = config.osw
        self.cm = config.cm

        _device_type_title = self.osw.site.semantic_search(
            f"[[-HasDeviceType::Item:{self.osw.get_osw_id(self.uuid)}]]"
        )
        self._device_type = self.osw.load_entity(_device_type_title[0]).cast(
            model.DataDevice
        )

        self._data_schemas = {}
        for source in self._device_type.data_sources:
            schema_page = self.osw.site.get_WtPage(source.type)
            schema_data = schema_page.get_slot_content("jsondata")
            self._data_schemas[str(source.uuid)] = schema_data["name"]

        print("Data Sources Schemas:")
        print(self._data_schemas)

        self._data_base = self.osw.load_entity(self._device_type.storage_location[0])
        self._data_base = self._data_base.cast(TimescaleDbController)
        self._data_base.connect(
            DatabaseController.ConnectionConfig(cm=self.cm, osw=self.osw)
        )

    class DataParam(OswBaseModel):
        """General param class"""

        source: Optional[model.DataSource]
        """explicite data source instance"""
        source_name: Optional[str]
        """the name of the source for name-matching"""
        # source_type: Optional[OswBaseModel]
        source_uuid: Optional[UUID]
        """the uuid of the source for uuid-matching"""
        timestamp: Optional[datetime]
        """the UTC timestamp of the dataset"""
        dataset: Optional[model.Dataset]
        """the dataset"""

    class StoreDataParam(DataParam):
        """Param class for get_source()"""

        dataset: model.Dataset
        """the data to store"""

        @validator("dataset")
        def check_dataset(cls, v):
            # print
            # if sum(v) > 42:
            #    raise ValueError('sum of numbers greater than 42')
            return v

    def get_source(self, param: DataParam):
        """Retrieves the data source from the given specification

        Parameters
        ----------
        param
            see StoreDataParam

        Returns
        -------
            the matched source or None

        Raises
        ------
        ValueError
            if no source was matching
        ValueError
            if more than one source was matching
        """

        source = None
        if param.source is not None:
            return param.source

        candidates = []
        for source in self._device_type.data_sources:
            if param.source_uuid and param.source_uuid == source.uuid:
                candidates.append(source)
            elif param.source_name and param.source_name == source.name:
                candidates.append(source)
            elif param.dataset and source.type in param.dataset.type:
                candidates.append(source)

        if len(candidates) > 1:
            raise ValueError(
                f"Ambiguous data source assignment: The specified configuration \n{print(param)}\n matches multiple data sources:\n{print(candidates)}"
            )
        if len(candidates) == 0:
            raise ValueError(
                f"Failed data source assignment: The specified configuration \n{print(param)}\n matches none of the data sources:\n{print(self._device_type.data_sources)}"
            )

        source = candidates[0]
        return source

    def store_data(self, param: StoreDataParam):
        """Stores the given data in the rool table

        Parameters
        ----------
        param
            see StoreDataParam
        """
        source = self.get_source(param)

        self._data_base.insert_tool_data(
            TimescaleDbController.InsertToolDataParam(
                tool=self, source=source, data=param.dataset
            )
        )

    class LoadDataParam(DataParam, TimescaleDbController.QueryToolDataParam):
        """Param class for load_data()"""

        tool: Optional[model.DataTool]  # overwrite to make it optional (autoset)
        """data tool (automatically set to the current instance)"""
        source: Optional[model.DataSource]  # overwrite to make it optional (autoset)
        """data source (automatically set if not specified)"""

    def load_data(self, param: LoadDataParam) -> List[DataParam]:
        """queries data from the tool table

        Parameters
        ----------
        param
            see LoadDataParam

        Returns
        -------
            query results as list of DataParams
        """
        param.source = self.get_source(param)
        param.tool = self
        raw_results = self._data_base.query_tool_data(param)
        results = []
        for res in raw_results:
            timestamp = res[0]
            jsondata = res[2]
            data = DataToolController.DataParam(
                timestamp=timestamp, source=param.source
            )
            if str(param.source.uuid) in self._data_schemas:
                data.dataset = eval(
                    f"model.{self._data_schemas[str(param.source.uuid)]}(**jsondata)"
                )
            else:
                data.dataset = model.Dataset(**jsondata)
            results.append(data)
        return results
