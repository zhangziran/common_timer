"""
author: cnk700i
blog: ljr.im
"""
import asyncio
import logging
import voluptuous as vol
import re
import time
from datetime import datetime,timedelta
import operator

from homeassistant import loader
from homeassistant import setup
from homeassistant.core import callback, Context

from homeassistant.components.sensor.template import SensorTemplate
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, CONF_ICON, CONF_NAME, CONF_MODE, EVENT_HOMEASSISTANT_START, EVENT_STATE_CHANGED, SERVICE_SELECT_OPTION, SERVICE_TURN_ON, SERVICE_TURN_OFF, EVENT_SERVICE_EXECUTED)

from homeassistant.helpers.config_validation import time_period_str
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util.async_ import (run_coroutine_threadsafe, run_callback_threadsafe)
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers import discovery
from homeassistant.helpers.template import Template
import homeassistant.helpers.config_validation as cv

from homeassistant.components.input_select import InputSelect
from homeassistant.components.input_boolean import InputBoolean
from homeassistant.components.input_text import InputText

_LOGGER = logging.getLogger(__name__)
# _LOGGER.setLevel(logging.DEBUG)

TIME_BETWEEN_UPDATES = timedelta(seconds=1)

DOMAIN = 'common_timer'
DEPENDENCIES = ['group']
ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_SET_OPTIONS = 'set_options'
SERVICE_SET_VALUE = 'set_value'
SERVICE_SELECT_OPTION = 'select_option'

UI_INPUT_DOMAIN = 'input_domain'
UI_INPUT_ENTITY = 'input_entity'
UI_INPUT_OPERATION = 'input_operation'
UI_INPUT_DURATION = 'input_duration'
UI_SWITCH = 'switch'

SERVICE_SET = 'set'
SERVICE_CANCEL = 'cancel'

CONF_OBJECT_ID = 'object_id'
CONF_UI = 'ui'
CONF_VISIBLE = 'visible'
CONF_VIEW = 'view'
CONF_INITIAL = 'initial'
CONF_PATTERN = 'pattern'
CONF_OPTIONS = 'options'
CONF_USE_FOR = 'use_for'
CONF_MIN = 'min'
CONF_MAX = 'max'
CONF_INFO_NUM_MIN = 'info_num_min'
CONF_INFO_NUM_MAX = 'info_num_max'
CONF_DOMAINS = 'domains'
CONF_EXCLUDE = 'exclude'
CONF_PATTERN = 'pattern'
CONF_FRIENDLY_NAME = 'friendly_name'
CONF_INFO_PANEL = 'info_panel'
CONF_RATIO = 'ratio'
CONF_LOOP_FLAG = '⟳'

ATTR_OBJECT_ID = 'object_id'
ATTR_NAME ='name'
ATTR_ENTITIES = 'entities'
ATTR_CALLER = 'caller'

PLATFORM_KEY = ('template', None, 'common_timer')
CONTEXT = Context()

INFO_PANEL_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default='ct_info_panel'): cv.string,
    vol.Optional(CONF_FRIENDLY_NAME, default='定时任务列表'): cv.string,
    vol.Optional(CONF_INFO_NUM_MIN, default=1): cv.positive_int,
    vol.Optional(CONF_INFO_NUM_MAX, default=10): cv.positive_int
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, default='ct_control_panel'): cv.string,
        vol.Optional(CONF_DOMAINS, default=['light', 'switch', 'input_boolean', 'automation', 'script']): vol.All(cv.ensure_list, vol.Length(min=1), [cv.string]),
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(cv.ensure_list, vol.Length(min=0), [cv.string]),
        vol.Optional(CONF_FRIENDLY_NAME, default='通用定时器'): cv.string,
        vol.Optional(CONF_INFO_PANEL, default={'name': 'ct_info_panel','friendly_name': '定时任务列表','info_num_min': 1,'info_num_max': 10}): INFO_PANEL_SCHEMA,
        vol.Optional(CONF_PATTERN, default='[\u4e00-\u9fa5]+'): cv.string,
        vol.Optional(CONF_RATIO, default=5): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_DURATION = 'duration'
ATTR_OPERATION = 'operation'
ATTR_IS_LOOP = 'is_loop'
COMMON_TIMER_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_DURATION, default=timedelta(minutes = 30)): cv.time_period,
    vol.Optional(ATTR_OPERATION, default='off'): cv.string,
    vol.Optional(ATTR_IS_LOOP, default=False): cv.boolean
})

BUILT_IN_CONFIG = {
    'ui': {
        'input_select': {
            'ct_domain': {
                'name': '设备类型',
                'options': ['请选择设备类型'],
                'initial': '请选择设备类型',
                'icon': 'mdi:format-list-bulleted-type',
                'use_for': 'input_domain'
            },
            'ct_entity': {
                'name': '设备名称',
                'options': ['请选择设备'],
                'initial': '请选择设备',
                'icon': 'mdi:format-list-checkbox',
                'use_for': 'input_entity'
            },
            'ct_operation': {
                'name': '操作',
                'options': ['开', '关', '开⇌关[1:x]', '关⇌开[1:x]'],
                'initial': '关',
                'icon': 'mdi:nintendo-switch',
                'use_for': 'input_operation'
            }
        },
        'input_text': {
            'ct_duration': {
                'name': '延迟时间',
                'initial': '0:00:00',
                'pattern': '([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]',
                'min': 0,
                'max': 8,
                'use_for': 'input_duration'
            }
        },
        'input_boolean': {
            'ct_switch': {
                'name': '启用/暂停',
                'initial': False,
                'icon': 'mdi:switch',
                'use_for': 'switch'
            }
        },
        'sensor': [{
            'platform': 'template',
            'entity_namespace': "common_timer",
            'sensors': {
                'ct_record_0': {
                    'friendly_name': "无定时任务",
                    'value_template': Template("-"),
                    'icon_template': Template("mdi:calendar-check")
                }
            }
        }]
    },
    # 'domains': ['light', 'switch', 'automation', 'script', 'input_boolean'],
    # 'exclude': [],
    # 'pattern': '[\u4e00-\u9fa5]+',
    # 'name': 'ct_control_panel',
    # 'friendly_name': '通用定时器',
    # 'info_panel': {
    #     'name': 'ct_info_panel',
    #     'friendly_name': '定时任务列表',
    #     'info_num_min': 1,
    #     'info_num_max': 10,
    # }
}

@asyncio.coroutine
def async_setup(hass, config):
    _LOGGER.debug("-------%s--------",config[DOMAIN])
    """ setup up common_timer component """
    ui ={}    #save params of input components for getting input

    VALIDATED_CONF = BUILT_IN_CONFIG[CONF_UI]
    info_ui = []
    #remove CONF_USE_FOR from BUILT_IN_CONFIG, otherwise raise a validate failure
    for domain in VALIDATED_CONF:
        if isinstance(VALIDATED_CONF[domain], list):
            for object_id in VALIDATED_CONF[domain][0]['sensors']:
                info_ui.append('{}.{}'.format(domain, object_id))
        else:
            for object_id in VALIDATED_CONF[domain]:        
                if CONF_USE_FOR in VALIDATED_CONF[domain][object_id]:
                    user_for = VALIDATED_CONF[domain][object_id][CONF_USE_FOR]
                    ui[user_for] = '{}.{}'.format(domain, object_id)
                    VALIDATED_CONF[domain][object_id].pop(CONF_USE_FOR)

    components = set(key.split(' ')[0] for key in config.keys())
    for setup_domain in ['input_select', 'input_text', 'input_boolean', 'sensor']:
        #config file contains info, let HA initailize 
        if setup_domain in components:
            _LOGGER.debug('initialize component[%s]: config has this component', setup_domain)
            #wait for HA initialize component
            #maybe it can use discovery.discover(hass, service='load_component.{}'.format(setup_domain), discovered={}, component=setup_domain, hass_config=config) instead
            while setup_domain not in hass.config.components:
                yield from asyncio.sleep(1)
                _LOGGER.debug("initialize component[%s]: wait for HA initialization.", setup_domain)

            if setup_domain in ['input_select', 'input_text', 'input_boolean']: #entity belongs to component
                _LOGGER.debug("initialize component[%s]: component is ready, use component's method.", setup_domain)
                #add entity in component
                entities = []
                for object_id, conf in VALIDATED_CONF.get(setup_domain, {}).items():
                    # _LOGGER.debug("setup %s.%s", setup_domain, object_id)
                    if setup_domain == 'input_select':
                        # InputSelect(object_id, name, initial, options, icon)
                        entity = InputSelect(object_id, conf.get(CONF_NAME, object_id), conf.get(CONF_INITIAL), conf.get(CONF_OPTIONS) or [], conf.get(CONF_ICON))
                    elif setup_domain == 'input_text':
                        # InputText(object_id, name, initial, minimum, maximum, icon, unit, pattern, mode)
                        entity = InputText(object_id, conf.get(CONF_NAME, object_id), conf.get(CONF_INITIAL), conf.get(CONF_MIN), conf.get(CONF_MAX), conf.get(CONF_ICON), conf.get(ATTR_UNIT_OF_MEASUREMENT), conf.get(CONF_PATTERN), conf.get(CONF_MODE))
                    elif setup_domain == 'input_boolean':
                        # InputBoolean(object_id, name, initial, icon)
                        entity = InputBoolean(object_id, conf.get(CONF_NAME), conf.get(CONF_INITIAL), conf.get(CONF_ICON))
                        _LOGGER.debug("input_boolean.timer_button:%s,%s,%s,%s", object_id, conf.get(CONF_NAME), conf.get(CONF_INITIAL), conf.get(CONF_ICON))
                    else:
                        pass
                        # _LOGGER.debug("illegal component:%s", object_id, conf.get(CONF_NAME), conf.get(CONF_INITIAL), conf.get(CONF_ICON))
                    entities.append(entity)
                # _LOGGER.debug("entities:%s", entities)
                yield from hass.data[setup_domain].async_add_entities(entities)        
                _LOGGER.debug('initialize component[%s]: entities added.', setup_domain)
            elif setup_domain in ['sensor']:   #entity belongs to component.platform 
                _LOGGER.debug("initialize component.platform[%s]: component is ready, use EntityComponent's method to initialize entity.", setup_domain)
                # should set a unique namespace to ensure it's a new platform and don't affect other entities using template platform which have been initialized.
                yield from hass.data[setup_domain].async_setup({setup_domain: VALIDATED_CONF.get(setup_domain, {})})
            else:
                _LOGGER.debug("initialize component[%s]: undefined initialize method.", setup_domain)

        #add config for HA to initailize
        else:
            _LOGGER.debug('initialize component[%s]: config hasn\'t this componet , use HA\'s setup method to initialize entity.', setup_domain)
            hass.async_create_task(setup.async_setup_component(hass, setup_domain, VALIDATED_CONF))

    #add group through service since HA initialize group by defalut
    data = {
        ATTR_OBJECT_ID: config[DOMAIN][CONF_NAME],
        ATTR_NAME: config[DOMAIN][CONF_FRIENDLY_NAME],
        ATTR_ENTITIES: [entity_id for param, entity_id in ui.items()]
        }
    # data[ATTR_ENTITIES].append('timer.laundry')
    yield from hass.services.async_call('group', SERVICE_SET, data)
    # hass.async_add_job(hass.services.async_call('group', SERVICE_SET, data))
    _LOGGER.debug('---control planel initialized---')

    #info panel inital
    info_config = config[DOMAIN].get(CONF_INFO_PANEL)
    if info_config:
        entities = []
        for num in range(1, info_config[CONF_INFO_NUM_MIN]):
            object_id = 'ct_record_{}'.format(num)
            state_template = Template('-')
            state_template.hass = hass
            icon_template = Template('mdi:calendar-check')
            icon_template.hass = hass
            entity = SensorTemplate(hass = hass,
                                    device_id = object_id,
                                    friendly_name = '无定时任务',
                                    friendly_name_template = None,
                                    unit_of_measurement = None,
                                    state_template = state_template,
                                    icon_template = icon_template,
                                    entity_picture_template = None,
                                    entity_ids = set(),
                                    device_class = None)

            entities.append(entity)
            info_ui.append(entity.entity_id)
        yield from hass.data['sensor']._platforms[PLATFORM_KEY].async_add_entities(entities)
        data = {
            ATTR_OBJECT_ID: info_config[CONF_NAME],
            ATTR_NAME: info_config[CONF_FRIENDLY_NAME],
            ATTR_ENTITIES: [entity_id for entity_id in info_ui]
            }
        yield from hass.services.async_call('group', SERVICE_SET, data)
        _LOGGER.debug('---info planel initialized---')

    domains = config[DOMAIN].get(CONF_DOMAINS)
    exclude = config[DOMAIN].get(CONF_EXCLUDE)
    pattern = config[DOMAIN].get(CONF_PATTERN)
    ratio = config[DOMAIN].get(CONF_RATIO)
    exclude.append(ui['switch']) # ignore ui input_boolean

    @callback
    def start_common_timer(event):
        """ initialize common_timer. """
        _LOGGER.debug('start initialize common_timer.')
        common_timer = CommonTimer(domains, exclude, pattern, ratio, ui, hass, info_config)
        
        @callback
        def common_timer_handle(event):
            """Listen for state changed events and refresh ui. """
            if event.data[ATTR_ENTITY_ID] == ui[UI_INPUT_DOMAIN]:
                # _LOGGER.debug('set domain from %s to %s',event.data['old_state'].as_dict()['state'] ,event.data['new_state'].as_dict()['state'])
                common_timer.choose_domain(event.data['new_state'].as_dict()['state'])
            elif event.data[ATTR_ENTITY_ID] == ui[UI_INPUT_ENTITY]:
                # _LOGGER.debug('set entity')
                common_timer.choose_entity(event.data['new_state'].as_dict()['state'])
            elif event.data[ATTR_ENTITY_ID] == ui[UI_INPUT_OPERATION]:
                # _LOGGER.debug('set operation')
                common_timer.choose_operation(event.data['new_state'].as_dict()['state'])
            elif event.data[ATTR_ENTITY_ID] == ui[UI_INPUT_DURATION]:
                pass
                # _LOGGER.debug('set time')
                # common_timer.input_duration(event.data['new_state'].as_dict()['state'])
            elif event.data[ATTR_ENTITY_ID] == ui[UI_SWITCH]:
                # _LOGGER.debug('start/stop')
                common_timer.switch(event.data['new_state'].as_dict()['state'])
            else:
                # _LOGGER.debug('start/stop')
                if common_timer.stop_loop_task(event.data[ATTR_ENTITY_ID], context = event.context):
                    hass.async_add_job(common_timer.update_info)
        hass.bus.async_listen(EVENT_STATE_CHANGED, common_timer_handle)

        @asyncio.coroutine
        def async_handler_service(service):
            """ Handle calls to the common timer services. """
            entity_id = service.data[ATTR_ENTITY_ID]
            duration = str(service.data[ATTR_DURATION])
            operation = service.data[ATTR_OPERATION]
            is_loop = service.data[ATTR_IS_LOOP]
            if service.service == SERVICE_SET:
                common_timer.set_task(entity_id, operation, duration, is_loop)
                pass
            elif service.service == SERVICE_CANCEL:
                common_timer.cancel_task(entity_id)
                pass
        hass.services.async_register(DOMAIN, SERVICE_SET, async_handler_service, schema=COMMON_TIMER_SERVICE_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_CANCEL, async_handler_service, schema=COMMON_TIMER_SERVICE_SCHEMA)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_common_timer)

    # for test
    # @callback
    # def service_executed(event):
    #     if event.context == CONTEXT:
    #         _LOGGER.debug("-----common_timer调用服务完毕！-----context = %s", CONTEXT)
    # hass.bus.async_listen(EVENT_SERVICE_EXECUTED, service_executed)

    return True
    
class CommonTimer:
    """Representation of a common timer."""
    def __init__(self, domains, exclude, pattern, ratio, ui, hass = None, info_config = None):
        """Initialize a common timer."""
        self._domains = domains
        self._exclude = exclude
        self._pattern = pattern
        self._ratio = ratio
        self._hass = hass
        self._ui = ui
        self._store = {}
        self._dic_friendly_name = {}
        self._dic_operation = {
            'on':'开',
            'off':'关',
            'temporary_on':'关⇌开[1:x]',
            'temporary_off': '开⇌关[1:x]',
            '关⇌开[1:x]':'temporary_on',
            '开⇌关[1:x]': 'temporary_off',            
            '开':'on',
            '关':'off'}
        self._dic_icon = {'light': 'mdi:lightbulb', 'switch': 'mdi:toggle-switch', 'automation': 'mdi:playlist-play', 'script': 'mdi:script', 'input_boolean': 'mdi:toggle-switch'}
        self._domain = None
        self._entity_id = None
        self._queue = DelayQueue(60)  # create a queue
        self._running_tasks = None
        self._running_tasks_ids = None
        self._info_config = info_config
        self.start()
        
    def start(self):
        """prepare task list and default ui. """
        pattern = re.compile(self._pattern)
        states = self._hass.states.async_all()

        for state in states:
            domain = state.domain
            object_id = state.object_id
            entity_id = '{}.{}'.format(domain, object_id)
            if domain not in self._domains or entity_id in self._exclude:
                pass
            else:
                friendly_name = state.name
                if not self._pattern or pattern.search(friendly_name):
                    _LOGGER.debug("添加设备:{}（{}）".format(friendly_name, entity_id))
                    self._dic_friendly_name.setdefault(friendly_name, entity_id)
                    self._store.setdefault(domain,{}).setdefault(entity_id,{})
                    self._store[domain][entity_id]['friendly_name'] = friendly_name                 
                    self._store[domain][entity_id]['icon'] = self.get_attributes(entity_id).get('icon', self._dic_icon[domain])
                    self._store[domain][entity_id]['entity_id'] = entity_id
                    self._store[domain][entity_id]['duration'] = '0:00:00'
                    self._store[domain][entity_id]['remaining'] = '0:00:00'
                    self._store[domain][entity_id]['handle'] = None
                    self._store[domain][entity_id]['operation'] = 'on' if domain == 'autonmation' or domain == 'script' else 'off'
                    self._store[domain][entity_id]['next_operation'] = None
                else:
                    _LOGGER.debug("忽略设备：{}（{}）".format(friendly_name, entity_id))
        options= list(self._store.keys())
        options.insert(0,'请选择设备类型')
        data = {
            'entity_id':self._ui[UI_INPUT_DOMAIN],
            'options': options
        }
        self._hass.async_add_job(self._hass.services.async_call('input_select', SERVICE_SET_OPTIONS, data))
        
        async_track_time_change(self._hass, self.update) # update every second


    def choose_domain(self, domain):
        """refresh entity input list """
        self._domain = domain
        if domain == '请选择设备类型':
            options = '请选择设备'
        else:
            options = [self._get_task(entity_id)['friendly_name'] for entity_id in self._store[domain]]  #show friendly_name
            options.insert(0,'请选择设备')
            self.set_options(self._ui[UI_INPUT_ENTITY], options)
    
    def choose_entity(self, friendly_name):
        """ load entity task params and set ui."""
        if friendly_name == '请选择设备':
            self._entity_id = None
            self.set_state(self._ui[UI_INPUT_DURATION], state= '0:00:00')
            self.set_state(self._ui[UI_SWITCH], state = 'off')
        else:
            entity_id = self._entity_id = self._dic_friendly_name.get(friendly_name, None)
            task = self._get_task(entity_id)
            if task is None:
                _LOGGER.info("Function choose_entity: friendly_name not found in dic !")
                return
            remaining_time = self._queue.get_remaining_time(task['handle'])
            # task's running
            if remaining_time is not None:
                duration = str(remaining_time)
                self.set_state(self._ui[UI_INPUT_DURATION], state= duration)
                self.set_state(self._ui[UI_SWITCH], state = 'on')
            else:
                duration = task['remaining'] if task['remaining'] != '0:00:00' else task['duration']
                self.set_state(self._ui[UI_INPUT_DURATION], state= duration)
                self.set_state(self._ui[UI_SWITCH], state = 'off')
            self.set_state(self._ui[UI_INPUT_OPERATION], state = self._dic_operation.get(task['operation']))

    def choose_operation(self, operation):
        """ set operation param """
        task = self._get_task(self._entity_id)
        if task is None:
            _LOGGER.debug("no entity selected, pass.")
            return
        # save operation if task is not running
        if self.get_state(self._ui[UI_SWITCH]) == 'off':
            task['operation'] = self._dic_operation.get(operation)
    
    def switch(self, state):
        """ start or stop task """
        if self._domain != '请选择设备类型':
            entity_id = self._entity_id
            task = self._get_task(self._entity_id)
            if task is None:
                _LOGGER.debug("未选择设备/未找到对应entity_id")
                self.set_state(self._ui[UI_SWITCH], state = 'off')
                return
            else:
                duration = self.get_state(self._ui[UI_INPUT_DURATION])
                operation = self._dic_operation.get(self.get_state(self._ui[UI_INPUT_OPERATION]))

                if duration == '0:00:00':
                    return
                # start timer
                if state == 'on':
                    if task['handle'] is None:
                        if task['remaining'] != duration:
                            task['duration'] = duration  # set duration attr
                        task['handle'] = self._queue.insert(entity_id, duration, self.handle_task, operation = operation)  # initialize queue task
                        task['operation'] = operation  #set operation attr

                        # sync state for loop task
                        if 'temporary' in operation:
                            task['next_operation'] = operation.split('_')[1]  # set next_operation attr, used in info panenl to show state
                            state = 'off' if task['next_operation'] == 'on' else 'on'
                            self.set_state(entity_id, state = state, service = 'turn_'+state, force_update = True) 
                            #service.call()
                        else:
                            task['next_operation'] = operation
                        task['exec_time'] = datetime.now() + self._queue.get_remaining_time(task['handle'])
                # stop timer
                else:
                    self._queue.remove(task['handle'])
                    task['handle'] = None
                    task['next_operation'] = None
                    if 'temporary' not in task['operation']:
                        task['remaining'] = duration
                    else:
                        task['remaining'] = '0:00:00'
                        self.set_state(self._ui[UI_INPUT_DURATION], state = task['duration'])  # reset control panel ui
                    self.set_state(self._ui[UI_INPUT_OPERATION], state = self._dic_operation.get(task['operation']))  # reset control panel ui

        else:
            _LOGGER.debug("no device type selected")
            self.set_state(self._ui[UI_SWITCH], state = 'off')
        self._hass.async_add_job(self.update_info)  # refresh info panel

    def _get_task(self, entity_id):
        """ return task base info  """
        if entity_id is None:
            return None
        domain = entity_id.split('.')[0]
        if self._store.get(domain, None) is not None:
            return self._store.get(domain, None).get(entity_id, None)
        else:
            return None
    
    def get_state(self, entity_id):
        """ return entity state. """
        return self._hass.states.get(entity_id).as_dict()['state']
    def get_attributes(self, entity_id):
        """ return entity attributes. """
        return self._hass.states.get(entity_id).as_dict().get('attributes',{})

    def set_state(self, entity_id, state = None, attributes = None, service = None, force_update = False):
        """ set entity state. """
        _LOGGER.debug("handle set_state(): entity_id= {},from {} to {}".format(entity_id, self.get_state(entity_id), state))
        if service is None:
            attr = self.get_attributes(entity_id)
            if attributes is not None:
                attr.update(attributes)
            self._hass.states.async_set(entity_id, state, attr, force_update = force_update, context = CONTEXT)
        else:
            domain = entity_id.split('.')[0]
            _LOGGER.debug('call service, entity_id =%s, context = %s',entity_id, CONTEXT)
            attr = self.get_attributes(entity_id)
            if attributes is not None:
                attr.update(attributes)
            
            #change state directly with a context identification since call service can't pass context in code.
            self._hass.states.async_set(entity_id, state, attr, force_update = force_update, context = CONTEXT)
            #call service to controll device
            self._hass.async_add_job(self._hass.services.async_call(domain, service, {'entity_id': entity_id}, context= CONTEXT ))
         
    def set_options(self, entity_id, options):
        """ set options for input select  """
        domain = entity_id.split('.')[0]
        if domain != 'input_select':
            _LOGGER.debug('wrong service')
            return
        self._hass.async_add_job(self._hass.services.async_call(domain, SERVICE_SET_OPTIONS, {'entity_id': entity_id,'options': options}))

    @callback
    def update(self, time):
        """ queue step forward and refresh timer display. 
            define callback to run in main thread.
        """
        self._queue.next()  # queue handler
        # refresh timer display when task is running
        if self.get_state(self._ui[UI_SWITCH]) == 'on':
            entity_id = self._entity_id
            if entity_id is None:
                _LOGGER.info("Function task: friendly_name(%s) not found in dic !", entity_id)
                return
            task = self._get_task(entity_id)
            remaining_time = self._queue.get_remaining_time(task['handle'])
            # task finish
            if remaining_time is None:
                remaining_time = task['remaining']
                if remaining_time == '0:00:00':
                    self.set_state(self._ui[UI_INPUT_DURATION], state = task['duration'])
                else:
                    self.set_state(self._ui[UI_INPUT_DURATION], state = str(remaining_time))
                self.set_state(self._ui[UI_SWITCH], state = 'off')
            # task waite
            else:
                self.set_state(self._ui[UI_INPUT_DURATION], state = str(remaining_time))

    # @asyncio.coroutine
    def handle_task(self, entity_id, operation, **kwargs):
        """ handle task when time arrive.
            if handler take long time, use hass.async_add_job(func) to exec in another thread. 
        """
        _LOGGER.debug("handle_task(%s): operation = %s.", entity_id, operation)
        task = self._get_task(entity_id)
        task['handle'] = None
        task['remaining'] = '0:00:00'

        if operation == 'temporary_on':
            ratio = self._ratio if task['operation'] == operation else 1
            delay =int(time_period_str(task['duration']).total_seconds()*ratio)
            task['handle'] = self._queue.insert(entity_id, str(timedelta(seconds = delay)), self.handle_task, 'temporary_off')
            task['next_operation'] = 'off'
            task['exec_time'] = datetime.now() + self._queue.get_remaining_time(task['handle'])
            operation = 'on'
        elif operation == 'temporary_off':
            ratio = self._ratio if task['operation'] == operation else 1
            delay =int(time_period_str(task['duration']).total_seconds()*ratio)
            task['handle'] = self._queue.insert(entity_id, str(timedelta(seconds = delay)), self.handle_task, 'temporary_on')
            task['next_operation'] = 'on'
            task['exec_time'] = datetime.now() + self._queue.get_remaining_time(task['handle'])
            operation = 'off'            
        elif operation == 'custom':
            pass
        service = 'turn_'+operation
        state = operation
        self.set_state(entity_id, state = state, service = service, force_update = True)
        _LOGGER.debug("handle_task finish:{}({})".format(service,entity_id))
        # self._hass.async_add_job(self.long_time_task)  # for test

    def long_time_task(self):
        """ for test. """
        _LOGGER.debug("handle long time task, start")
        time.sleep(5)
        _LOGGER.debug("handle long time task, finish")
    
    def _get_index_of_running_tasks(self, entity_id):
        """ return index of running_tasks. """
        if entity_id is None or self._running_tasks_ids is None:
            return None
        try:
            row = self._running_tasks_ids.index(entity_id)
            return row
        except ValueError:
            return None

    def stop_loop_task(self, entity_id, context):
        """ if entity operated by other method, stop loop task.
            according context to identify who changes state of entity.
        """
        info_config = self._info_config
        if info_config is None:
            return False

        #if entity in running tasks list
        if self._get_index_of_running_tasks(entity_id) is not None:
            task = self._get_task(entity_id)
            #if loop task and who operated
            if 'temporary' in task['operation'] and context != CONTEXT:
                _LOGGER.debug("operated by other method. <entity_id = %s, context = %s>", entity_id, context)
                #clear task info
                self._queue.remove(task['handle'])
                task['handle'] = None
                task['remaining'] = '0:00:00'
                #reset frontend
                if self._entity_id == entity_id:
                    self.set_state(self._ui[UI_SWITCH], state = 'off')
                    self.set_state(self._ui[UI_INPUT_DURATION], state = task['duration'])                
            else:
                _LOGGER.debug("operated by common_timer.py. <entity_id = %s, context = %s>", entity_id, context)
            return True
        return False

    def _get_running_tasks(self):
        """get running tasks order by exec_time"""
        tasks = [attrs for entities in self._store.values() for entity_id, attrs in entities.items() if attrs['handle'] is not None]
        return sorted(tasks, key=operator.itemgetter('exec_time'))

    @asyncio.coroutine
    def update_info(self):
        """update info and refresh info panel."""
        info_config = self._info_config
        if info_config is None:
            return
        _LOGGER.debug("↓↓↓↓↓_update_info()↓↓↓↓↓")
        running_tasks = self._get_running_tasks()
        self._running_tasks_ids = [entity['entity_id'] for entity in running_tasks]
        info_row_num = len(running_tasks) if len(running_tasks) < info_config[CONF_INFO_NUM_MAX] else info_config[CONF_INFO_NUM_MAX]
        new_rows = []
        info_ui = []
        default_state = Template('-')
        default_state.hass = self._hass
        default_icon = Template('mdi:calendar-check')
        default_icon.hass = self._hass
        # refresh every row
        for row in range(0, info_config[CONF_INFO_NUM_MAX]):
            info_entity_id = 'sensor.ct_record_{}'.format(row)
            info_entity = self._hass.data['sensor'].get_entity(info_entity_id)
            # rows show record
            if row < info_row_num:
                _LOGGER.debug("info_entity:%s, row=%s",info_entity, row)
                # info1 = '{0:{2}<12}{1:{2}>20}'.format(running_tasks[row]['friendly_name'], running_tasks[row]['exec_time'].strftime("%Y-%m-%d %H:%M:%S"),chr(12288))  # for test
                info1 = '{}{}'.format(align(running_tasks[row]['friendly_name'],20), align(running_tasks[row]['exec_time'].strftime("%Y-%m-%d %H:%M:%S"),20))  # name+time info template
                loop_flag = CONF_LOOP_FLAG if 'temporary' in running_tasks[row]['operation'] else ''
                info2 = Template('{} {} → {}'.format(loop_flag, self.get_state(running_tasks[row]['entity_id']), running_tasks[row]['next_operation']))  # operation info template
                info2.hass = self._hass
                # info3 = Template('{{{{states.{}.{}.{}}}}}'.format(running_tasks[row]['entity_id'] ,'attributes' ,'icon'))  # for test
                info3 = Template(running_tasks[row]['icon'])  # icon template
                info3.hass = self._hass
                # row has record, update
                if info_entity is not None:
                    _LOGGER.debug("row%s, record exist. <info_entity_id= %s >",row,info_entity_id)
                    info_entity._name = info1
                    info_entity._template = info2
                    info_entity._icon_template = info3
                    info_entity.schedule_update_ha_state(True)  # force_refresh = True to call device_update to update sensor.template
                # row has record, add   
                else:
                    _LOGGER.debug("row%s, no record. <info_entity_id = %s, state = %s>",row,info_entity_id, self._dic_operation.get(running_tasks[row]['operation']))
                    object_id = 'ct_record_{}'.format(row)
                    sensor = SensorTemplate(hass = self._hass,
                                            device_id = object_id,
                                            friendly_name = info1,
                                            friendly_name_template = None,
                                            unit_of_measurement = None,
                                            state_template = info2,
                                            icon_template = info3,
                                            entity_picture_template = None,
                                            entity_ids = set(),
                                            device_class = None)
                    new_rows.append(sensor)
                info_ui.append(info_entity_id)
            # rows show blank or should be remove
            else:
                if not any([info_row_num, row]) or row < info_config[CONF_INFO_NUM_MIN] or info_config[CONF_INFO_NUM_MAX] == info_config[CONF_INFO_NUM_MIN]:
                    info1 = '无定时任务'
                    info_entity._name = info1
                    info_entity._template = default_state
                    info_entity._icon_template = default_icon
                    info_entity.schedule_update_ha_state(True)  # force_refresh = True to call device_update to update sensor.template
                    info_ui.append(info_entity_id)
                else:
                    yield from self._hass.data['sensor'].async_remove_entity(info_entity_id)
        if new_rows:
            yield from self._hass.data['sensor']._platforms[PLATFORM_KEY].async_add_entities(new_rows, update_before_add = True)

        data = {
            ATTR_OBJECT_ID: info_config[CONF_NAME],
            ATTR_NAME: info_config[CONF_FRIENDLY_NAME],
            ATTR_ENTITIES: [entity_id for entity_id in info_ui]
            }
        yield from self._hass.services.async_call('group', SERVICE_SET, data)
        _LOGGER.debug("↑↑↑↑↑_update_info()↑↑↑↑↑")

    def set_task(self, entity_id, operation, duration, is_loop):
        """ create new task, will overwrite previous task. """
        _LOGGER.debug('----set_task()-----')
        task = self._get_task(entity_id)
        if task is not None:
            self._queue.remove(task['handle'])
            task['duration'] = duration
            task['next_operation'] = operation
            if is_loop:
                operation = 'temporary_' + operation
                state = 'off' if task['next_operation'] == 'on' else 'on'
                self.set_state(entity_id, state = state, service = 'turn_'+state, force_update = True)
            task['operation'] = operation
            task['handle'] = self._queue.insert(entity_id, duration, self.handle_task, operation = operation)  # initialize queue task
            task['exec_time'] = datetime.now() + self._queue.get_remaining_time(task['handle'])
            self._hass.async_add_job(self.update_info)  # refresh info panel
            if self._entity_id == entity_id:
                self.set_state(self._ui[UI_INPUT_OPERATION], state = self._dic_operation.get(task['operation']))  # reset control panel ui
                self.set_state(self._ui[UI_INPUT_DURATION], state = task['duration'])
                self.set_state(self._ui[UI_SWITCH], state = 'on')
        else:
            _LOGGER.info('set up task for %s failure', entity_id)
    
    def cancel_task(self, entity_id):
        """ cancel task. """
        task = self._get_task(entity_id)
        if task is not None:
            self._queue.remove(task['handle'])
            task['handle'] = None
            task['remaining'] = '0:00:00'
            #reset frontend
            if self._entity_id == entity_id:
                self.set_state(self._ui[UI_SWITCH], state = 'off')
                self.set_state(self._ui[UI_INPUT_DURATION], state = task['duration'])
            self._hass.async_add_job(self.update_info)  # refresh info panel
        else:
            _LOGGER.info('cancel task of %s failure', entity_id)

class DelayQueue(object):
    """Representation of a queue. """
    __current_slot = 1

    def __init__(self, slots_per_loop, **kwargs):
        """initailize a queue. """
        self.__slots_per_loop = slots_per_loop
        self.__queue = [[] for i in range(slots_per_loop)]
    
    def insert(self, task_id, duration, callback, operation = 'turn_off', **kwargs):
        """ add new task into queue """
        if duration == "0:00:00":
            return None
        second = time_period_str(duration).total_seconds()
        loop = second / len(self.__queue)
        slot = (second + self.__current_slot - 1) % len(self.__queue)
        delayQueueTask = DelayQueueTask(task_id, operation, int(slot), loop, callback, kwargs = kwargs)
        self.__queue[delayQueueTask.slot].append(delayQueueTask)
        _LOGGER.debug("create task:{}/{}".format(delayQueueTask.slot, delayQueueTask.loop))
        return delayQueueTask

    def remove(self, delayQueueTask):
        """ remove task from queue """
        if delayQueueTask is not None:
            _LOGGER.debug("remove task in slot {}.".format(delayQueueTask.slot))
            self.__queue[delayQueueTask.slot].remove(delayQueueTask)
        else:
            _LOGGER.debug("remove task, but not found.")

    
    def get_remaining_time(self, delayQueueTask):
        """ return remaining time of task"""
        if delayQueueTask:
            if self.__current_slot - 1 > delayQueueTask.slot and self.__current_slot - 1 < 60:
                second = self.__slots_per_loop * (delayQueueTask.loop + 1) + delayQueueTask.slot - (self.__current_slot - 1)
            else:
                second = self.__slots_per_loop * delayQueueTask.loop + delayQueueTask.slot - (self.__current_slot - 1)
            return timedelta(seconds = second)
        else:
            return None
   
    def next(self):
        """ queue read tasks of current slot, and execute task when loop count of task arrives 0 """
        if len(self.__queue) >= self.__current_slot:
            tasks = self.__queue[self.__current_slot - 1]
            # _LOGGER.debug("current slot：{}(has {} tasks)".format(self.__current_slot - 1,len(tasks)))
            if tasks:
                executed_task = []
                for task in tasks:
                    _LOGGER.debug("find {} at loop:{}/{}, exec = {}".format(task.task_id, task.slot, task.loop, task.should_exec))
                    if task.should_exec:
                        task.exec_task()
                        executed_task.append(task)
                    else:
                        task.nextLoop()
                for task in executed_task:
                    # _LOGGER.debug("remove task in slot {}".format(task.slot))
                    tasks.remove(task)  #删除slot的任务，不是调用DelayQueue对象方法；因为引用同一对象，会同步删除
            self.__current_slot += 1
            if self.__current_slot > len(self.__queue):
                self.__current_slot = 1

class DelayQueueTask(object):
    """Representation of a queue task."""

    def __init__(self, task_id, operation:str = 'turn_off', slot:int = 0 , loop:int = 0 , exec_task = None, **kwargs):
        """initialize a queue task."""
        self._task_id = task_id
        self._operation = operation
        self._slot = int(slot)
        self._loop = int(loop)
        self._exec_task = exec_task
        self._kwargs = kwargs

    @property
    def slot(self) -> int:
        """ return slot """
        return int(self._slot)

    @property
    def loop(self) -> int:
        """ return loop """
        return int(self._loop)

    @property
    def task_id(self):
        """ return entity_id of task """
        return self._task_id

    @property
    def operation(self):
        """ return operatrion of task """
        return self._operation

    def nextLoop(self):
        """ update after queue finish a loop """
        self._loop -= 1

    @property
    def should_exec(self) -> bool:
        """ return true when loop count """
        if self._loop == 0:
            return True
        else:
            return False
    
    def exec_task(self):
        """ handle task"""
        self._exec_task(self._task_id, self._operation, kwargs = self._kwargs)


def is_chinese(uchar):
    """ return True if a unicode char is chinese. """
    if uchar >= u'\u4e00' and uchar <= u'\u9fa5':
        return True
    else:
        return False

def align( text, width, just = "left"):
    """ align strings mixed with english and chinese """
    utext = stext = str(text)
    # utext = stext.decode("utf-8")
    cn_count = 0
    for u in utext:
        if is_chinese(u):
            cn_count += 2 # count chinese chars width
        else:
            cn_count += 1  # count english chars width
    num =int( (width - cn_count) / 2 )
    blank =int( (width - cn_count) % 2)
    if just == "right":
        return chr(12288) * num + " " * blank + stext
    elif just == "left":
        return stext + " " * blank + chr(12288) * num
