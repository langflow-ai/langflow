from typing import Callable, List, Dict

from langchain_core.messages import BaseMessage
from lfx.log.logger import logger


def tool_guard_validation(fc: List[Dict], messages: List[BaseMessage], tool_specs: List[Callable]) -> Dict:
    """ stub function of an example tool guard """
    #print(f'function_call: {function_call}, tool_specs: {tool_specs}, messages: {messages}')

    func = fc[0]['function']['name']
    args = fc[0]['function']['arguments']

    logger.info(f'🔒️ToolGuard invocation for {func}: {func+"_guard"}')
    #print('in tool_guard_validation:', fc, messages, tool_specs)

    return evaluate_expression_guard(args)


def evaluate_expression_guard(args: str) -> Dict:
    if '/0' in args:  # division by zero
        result = {'valid': False, 'error_msg': 'error raised in tool guard code: division by zero is illegal\n'}
    else:
        result = {'valid': True, 'error_msg': None}
    return result

