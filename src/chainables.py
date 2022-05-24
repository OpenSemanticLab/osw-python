from pprint import pprint
import copy
import types
from jsonpath_ng.ext import parse
from abc import ABCMeta, abstractmethod
from pydantic import BaseModel, validator
from typing import List, Optional, Any, Union
import datetime

import asyncio

class Chainable:
    pass

#Todo: default params
#Todo: store secrets
class ChainableContext:
    def __init__(self):#, dryrun, debug):
        #self.dryrun = dryrun
        #self.debug = debug
        self.workflow = []

    def add_mapping(self, mapping):
        self.workflow.append(mapping)

    def run(self):
        return

class ChainableObjectHistory(BaseModel):
    func: Any#type(AbstractChainableFunction) #Union[ChainableFunction, TypeSafeChainableFunction]
    #data: Optional[Union[dict, TypeSafeChainableFunction.Data]] = None
    #param: Optional[Union[dict, TypeSafeChainableFunction.Param]] = None
    data: Optional[dict] = None
    param: Optional[dict] = None
    mapping: Optional[dict] = None
    
    @validator("func")
    def validate_some_foo(cls, val):
        if issubclass(type(val), AbstractChainableFunction):
            return val
        raise TypeError("Wrong type for 'func', must be subclass of AbstractChainableFunction")
    
class ChainableObject(BaseModel):
    data: Optional[dict] = {}
    meta: Optional[dict] = {}
    hist: Optional[List[ChainableObjectHistory]] = []
    mapping: Optional[dict] = {}
    emit: Optional[Any] = None#lambda obj: print("NOT IMPLEMENTED")

    def resolve(self, mapping):
        #make components availabel in function scobe
        data = self.data
        meta = self.meta
        #hist = self.hist
        for key in mapping['param']:
            res = []
            value = mapping['param'][key]
            if isinstance(value, dict): #dynamic
                if 'static' in value: res.append(value['static']) #explicit static 
                if 'eval' in value: res.append(eval(value['eval'])) #eval expression
                if 'jsonpath' in value:
                    jsonpath_expr = parse(value['jsonpath'])
                    for match in jsonpath_expr.find(self.dict()):
                        res.append(match.value)
                if 'match' in value:  #match condition
                    if 'meta' in value['match']:
                        jsonpath_expr = parse(value['match']['meta']['jsonpath'])
                        #[print(str(match.full_path)) for match in jsonpath_expr.find(self.content)]
                        #[pprint(match.value) for match in jsonpath_expr.find(obj.content)]
                        for match in jsonpath_expr.find(self.dict()):
                            data_path = str(match.full_path).replace('meta', 'data', 1) #default: replace only root key => traverse to data branch
                            if 'value' in value and 'data' in value['value']:
                                data_path = str(match.full_path).replace('meta', 'data', 1) 
                                if value['value']['data']['jsonpath'] != "": data_path += "." + value['value']['data']['jsonpath'] #value path relative to match path
                                res.append(parse(data_path).find(self.dict())[0].value)
                            if 'value' in value and 'meta' in value['value']:
                                data_path = str(match.full_path) + "." + value['value']['meta']['jsonpath'] #value path relative to match path
                                res.append(parse(data_path).find(self.dict())[0].value)
                            print(data_path)
                            #pprint(parse(data_path).find(self.content)[0].value)
                            
                if (len(res) == 1): res = res[0]
                mapping['param'][key] = res
            if isinstance(value, types.FunctionType) and not key.startswith('_'): #dynamic function
                mapping['param'][key] = value()
        return mapping
    
    def apply(self, mappings):
        if not isinstance(mappings, list):
            mappings = [mappings]
        for mapping in mappings:
            if mapping is None:
                mapping = self.mapping #read map from object (result from previous function)
            mapping = self.resolve(mapping)
            self = eval(mapping['func'] + ".apply(self, mapping['param'])")
        #raw_data(self.content, mapping)
        #pprint(mapping)
        #pprint(self.content)
        return self
    
    #Todo: consider file or db backends
    def store_data(self, key: str, data, meta):
        if not key in self.data: self.data[key] = []
        self.data[key].append(data)
        if not key in self.meta: self.meta[key] = []
        self.meta[key].append(meta)
        
    def store_hist(self, hist: ChainableObjectHistory):
        #hist.func.obj = None #prevent circular objects
        self.hist.append(hist)
        
class AbstractChainableFunction(BaseModel):
    name: str
    uuid: str
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    obj: Optional[ChainableObject] = None
        
    @abstractmethod
    def apply(self, obj, param):
        pass   
    
class ChainableFunction(AbstractChainableFunction):
    param_default: dict = {}
    
    def set_default_params(self, param: dict):
        self.param_default = param 
    
    def set_param(self, param: dict = None):        
        if not param is None:
            param = {**self.param_default, **param}
        else: param = self.param_default
        pprint(param)
        return param
    
    def apply(self, obj: ChainableObject, param: dict = None):
        self.obj = obj
        param = self.set_param(param)
        self.pre_exec(param)
        self.func(param)
        self.post_exec(param)
        return obj
    
    def pre_exec(self, param):
        self.start_time = datetime.datetime.utcnow()
    
    @abstractmethod
    def func(self, param):
        pass
    
    def store(self, key, data, meta):
        self.obj.store_data(key, data, meta)
        
    def post_exec(self, param):
        obj = self.obj
        #self.obj = None
        hist = {}
        #if param['debug']: hist['data'] = copy.deepcopy(obj.data)
        #if param['debug']: hist['mapping'] = copy.deepcopy(obj.mapping)
        self.end_time = datetime.datetime.utcnow()
        func = self.copy()
        func.obj = None
        hist['func'] = func
        hist['param'] = param
        obj.store_hist(ChainableObjectHistory(**hist))
    
class TypeSafeChainableFunction(AbstractChainableFunction):
    class Param(BaseModel):
        debug: bool = False
    class Data(BaseModel):
        pass
    class Meta(BaseModel):
        data_class: Optional[type(BaseModel)] = None  
        data_class_name: Optional[str] = ""  
        
    param_class: type(Param)# = TypeSafeChainableFunction.Param  
    data_class: Optional[type(Data)]
    meta_class: Optional[type(Meta)]
    
    def __init__(self, name: str, uuid: str, 
                 param_class: type(Param) = Param,
                 data_class: type(Data) = None,
                 meta_class: type(Meta) = None
                ): 
        assert type(param_class) == type(TypeSafeChainableFunction.Param) or issubclass(param_class, TypeSafeChainableFunction.Param)
        assert data_class == None or type(data_class) == type(TypeSafeChainableFunction.Data) or issubclass(data_class, TypeSafeChainableFunction.Data)
        assert meta_class == None or type(meta_class) == type(TypeSafeChainableFunction.Meta) or issubclass(meta_class, TypeSafeChainableFunction.Meta)
        super().__init__(name=name, uuid=uuid, param_class=param_class, data_class=data_class, meta_class=meta_class)

    def apply(self, obj, param):
        self.obj = obj
        param = self.param_class(**param)
        self.pre_exec(param)
        self.func(param)
        self.post_exec(param)
        return obj
    
    def pre_exec(self, param):
        self.start_time = datetime.datetime.utcnow()
    
    @abstractmethod
    def func(self, param: Param):
        pass
    
    def store(self, key: str, data, meta):
        if self.data_class != None:
            if type(data) != self.data_class:
                data = self.data_class(**data)
        if self.meta_class != None:
            if type(meta) != self.meta_class:
                meta = self.meta_class(data_class = self.data_class, data_class_name = self.__class__.__name__ + '.' + self.data_class.__name__, **meta)
        self.obj.store_data(key, data, meta)
        
    def post_exec(self, param):      
        hist = {}
        #if param['debug']: hist['data'] = copy.deepcopy(obj.data)
        #if param['debug']: hist['mapping'] = copy.deepcopy(obj.mapping)
        self.end_time = datetime.datetime.utcnow()
        func = self.copy()
        func.obj = None
        hist['func'] = func
        hist['param'] = param
        self.obj.store_hist(ChainableObjectHistory(**hist))  

class AsyncChainableContext(ChainableContext):
    async def run_async(self, workflow, obj = None):
        if (obj == None): obj = AsyncChainableObject()
        for step in workflow:
            obj = await obj.apply_parallel_async(step)
        return obj

class AsyncChainableObject(ChainableObject):
    done: Any = None
    async def apply_async(self, mapping: Union[dict, List[dict]]):
        #print("start")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, super(__class__, self).apply, mapping)
        #print("stop")
        return self
        
    async def apply_parallel_async(self, mappings: Union[dict, List[dict]], timeout = None):
        if not isinstance(mappings, list):
            mappings = [mappings]
        jobs = []
        for mapping in mappings:
            jobs.append(self.apply_async(mapping))
        group_task = asyncio.gather(*jobs)
    
        try:
            if timeout == None: result = await group_task
            else: result = await asyncio.wait_for(group_task, 3)
            #print (result)
        except asyncio.CancelledError:
            print("Gather was cancelled")
        except asyncio.TimeoutError:
            print("Time's up!")
        
        #self.done(self)
        return self
    
    def apply_parallel(self, mappings: List[dict], timeout = None):
        #asyncio.run(testFunc())
        loop = asyncio.get_running_loop()
        tsk = loop.create_task(self.apply_parallel_async(mappings, timeout))
        tsk.add_done_callback(lambda t: t.result().done(t.result()))#(lambda t: print(f'Task done with result={t.result()}  << return val of main()'))
        return self
        
    def apply_sequential_async(self, mappings):
        #super(__class__, self).apply
        return self.apply_async(mappings)
    
    def apply_sequential(self, mappings):
        return self.apply(mappings)
    
class AsyncChainableEventFunction(ChainableFunction):    
    @abstractmethod    
    async def loop(self, param):
        pass
        
    def func(self, param):
        #asyncio.run(self.loop()) #for standard python
        loop = asyncio.get_running_loop() #for jupyter / ipython
        tsk = loop.create_task(self.loop(param))
        
    def emit(self):
        org_obj = copy.deepcopy(self.obj)
        self.obj.emit(org_obj)