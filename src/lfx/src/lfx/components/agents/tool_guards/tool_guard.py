from lfx.log.logger import logger


def tool_guard_validation(fc, messages, tool_specs):
    """ stub function of an example tool guard """
    #print(f'function_call: {function_call}, tool_specs: {tool_specs}, messages: {messages}')

    func = fc[0]['function']['name']
    args = fc[0]['function']['arguments']

    logger.info(f'invoking ToolGuard for {func}: {func+"_guard"}')

    return evaluate_expression_guard(args)


def evaluate_expression_guard(args):
    if '/0' in args:  # division by zero
        result = {'valid': False, 'error_msg': 'error running tool guard code\n'}
    else:
        result = {'valid': True, 'error_msg': None}
    return result
    
