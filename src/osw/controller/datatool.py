from datetime import datetime
from typing import List, Optional, Union
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

    _data_schemas: List[Optional[model.Dataset]]
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
        print(self._device_type)

        self._data_base = self.osw.load_entity(self._device_type.storage_location[0])
        self._data_base = self._data_base.cast(TimescaleDbController)
        self._data_base.connect(
            DatabaseController.ConnectionConfig(cm=self.cm, osw=self.osw)
        )

    class DataParam(OswBaseModel):
        source: Optional[model.DataSource]
        source_name: Optional[str]
        # source_type: Optional[OswBaseModel]
        source_uuid: Optional[UUID]
        timestamp: Optional[datetime]
        dataset: Optional[model.Dataset]

    class StoreDataParam(DataParam):
        dataset: model.Dataset

        @validator("dataset")
        def check_dataset(cls, v):
            # print
            # if sum(v) > 42:
            #    raise ValueError('sum of numbers greater than 42')
            return v

    def get_source(self, param: DataParam):
        source = None
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
        source = self.get_source(param)

        self._data_base.insert_tool_data(
            TimescaleDbController.InsertToolDataParam(
                tool=self, source=source, data=param.dataset
            )
        )

    class LoadDataParam(DataParam, TimescaleDbController.QueryToolDataParam):
        tool: Optional[model.DataTool]  # overwrite to make it optional (autoset)
        source: Optional[model.DataSource]  # overwrite to make it optional (autoset)

    def load_data(self, param: LoadDataParam) -> List[DataParam]:
        param.source = self.get_source(param)
        param.tool = self
        raw_results = self._data_base.query_tool_data(param)
        results = []
        for res in raw_results:
            data = DataToolController.DataParam(
                timestamp=res[0], source=param.source, dataset=model.Dataset(**res[2])
            )
            results.append(data)
        return results
