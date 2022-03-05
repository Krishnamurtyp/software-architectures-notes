import logging
from typing import (
    Callable,
    Dict,
    List,
    Type,
    Union,
)

from src.domain import (
    commands,
    events,
)
from src.service_layer import (
    handlers,
    unit_of_work,
)

logger = logging.getLogger(__name__)

Message = Union[commands.Command, events.Event]

EVENT_HANDLERS: Dict[Type[events.Event], List[Callable]] = {
    events.OutOfStock: [handlers.send_out_of_stock_notification],
    events.Allocated: [handlers.publish_allocated_event, handlers.add_allocation_to_read_model],
    events.Deallocated: [handlers.remove_allocation_from_read_model, handlers.reallocate]
}

COMMAND_HANDLERS: Dict[Type[commands.Command], Callable] = {
    commands.CreateBatch: handlers.add_batch,
    commands.ChangeBatchQuantity: handlers.change_batch_quantity,
    commands.Allocate: handlers.allocate,
}


def handle(message: Message, uow: unit_of_work.AbstractUnitOfWork):
    results = []
    queue = [message]
    while queue:
        message = queue.pop(0)
        if isinstance(message, events.Event):
            _handle_event(message, queue, uow)
        elif isinstance(message, commands.Command):
            results.append(_handle_command(message, queue, uow))
        else:
            raise Exception(f"{message} was not an Event or Command")
    return results


def _handle_event(event: events.Event, queue: List[Message], uow: unit_of_work.AbstractUnitOfWork):
    for handler in EVENT_HANDLERS[type(event)]:
        try:
            logger.debug(f"Handling event {event} with handler {handler}")
            handler(event, uow=uow)
            queue.extend(uow.collect_new_messages())
        except Exception as e:
            logger.exception(f"Exception handling event {event}: {e}")
            continue


def _handle_command(command: commands.Command, queue: List[Message], uow: unit_of_work.AbstractUnitOfWork):
    try:
        handler = COMMAND_HANDLERS[type(command)]
        result = handler(command, uow=uow)
        queue.extend(uow.collect_new_messages())
        return result
    except Exception:
        logger.exception("Exception handling command %s", command)
        raise
