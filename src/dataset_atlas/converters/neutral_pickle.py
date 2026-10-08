"""Inert pickle syntax: GLOBAL/REDUCE/BUILD become data nodes; no serialized code runs.

This reader imports no source-referenced module, invokes no source callable and
constructs no source class. It is used only inside the bounded FACTOID converter.
"""
from __future__ import annotations
import gzip
import pickletools
import re
import time
from typing import Any, Callable, IO, cast
from pathlib import Path

class Symbol:
    def __init__(self, module, name):
        if not isinstance(module, str) or not isinstance(name, str) or len(module) + len(name) > 512 or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', module) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', name):
            raise ValueError('Unsupported serialization symbol; nothing was executed')
        self.module, self.name = module, name

class Node:
    def __init__(self, symbol: Any, args: Any, kind: str):
        if not isinstance(symbol, (Symbol, Node)):
            raise ValueError('Serialization callable is not a neutral symbol')
        self.symbol, self.args, self.kind = symbol, args, kind
        self.state: Any = None

class Limited:
    def __init__(self, stream, check):
        self.stream, self.total, self.check, self.reads = stream, 0, check, 0
    def bounded_check(self):
        self.reads += 1
        if self.reads % 10000 == 0:
            self.check()
    def read(self, count=-1):
        self.bounded_check()
        if count >= 1_000_000:
            self.check()
        if not 0 <= count <= 32_000_000:
            raise ValueError('Serialization read exceeds 32 MB literal bound')
        self.total += count
        if self.total > 2_000_000_000:
            raise ValueError('Serialization exceeds 2 GB decoded bound')
        return self.stream.read(count)
    def readline(self):
        self.bounded_check()
        result = self.stream.readline(32769)
        self.total += len(result)
        if len(result) > 32768 or self.total > 2_000_000_000:
            raise ValueError('Serialization line exceeds its bound')
        return result

def parse_gzip(path: Path, check: Callable[[], None] = lambda: None, *, shared_ids: dict[int, int] | None = None):
    stack: list[Any] = []
    memo: dict[int, Any] = {}
    symbols: set[str] = set()
    mark = object()
    deadline = time.monotonic() + 240
    ops = 0
    def guard():
        check()
        if time.monotonic() > deadline:
            raise ValueError('Neutral serialization exceeds its time budget')
    guard()
    def need(count):
        if len(stack) < count or any(value is mark for value in stack[-count:]):
            raise ValueError('Serialization operand stack underflow or misplaced mark')
    def marked():
        index = len(stack) - 1
        while index >= 0 and stack[index] is not mark:
            index -= 1
        if index < 0:
            raise ValueError('Missing serialization mark')
        result = stack[index+1:]
        del stack[index:]
        return result
    with gzip.open(path, 'rb') as raw:
        stream = Limited(raw, guard)
        for opcode, value, position in pickletools.genops(cast(IO[bytes], stream)):
            ops += 1
            if ops % 10000 == 0:guard()
            if ops > 180_000_000 or (ops % 10000 == 0 and time.monotonic() > deadline):
                raise ValueError('Neutral serialization probe exceeds operation/time budget')
            op = opcode.name
            if op in {'PROTO', 'FRAME'}:
                continue
            elif op == 'MARK':stack.append(mark)
            elif op in {'SHORT_BINUNICODE', 'BINUNICODE', 'BINUNICODE8', 'UNICODE', 'STRING', 'BINSTRING', 'SHORT_BINSTRING',
                        'BININT', 'BININT1', 'BININT2', 'INT', 'LONG', 'LONG1', 'LONG4', 'BINFLOAT', 'FLOAT',
                        'SHORT_BINBYTES', 'BINBYTES', 'BINBYTES8'}:stack.append(value)
            elif op == 'BYTEARRAY8':
                if not isinstance(value, (bytes, bytearray)):raise ValueError('Invalid bytearray operand')
                stack.append(bytearray(value))
            elif op == 'NONE':stack.append(None)
            elif op == 'NEWTRUE':stack.append(True)
            elif op == 'NEWFALSE':stack.append(False)
            elif op == 'EMPTY_LIST':stack.append([])
            elif op == 'EMPTY_DICT':stack.append({})
            elif op == 'EMPTY_TUPLE':stack.append(())
            elif op == 'TUPLE':stack.append(tuple(marked()))
            elif op in {'TUPLE1', 'TUPLE2', 'TUPLE3'}:
                size = int(op[-1]);need(size);values = stack[-size:];del stack[-size:];stack.append(tuple(values))
            elif op == 'LIST':stack.append(marked())
            elif op == 'DICT':
                values = marked();stack.append(dict(zip(values[::2], values[1::2], strict=True)))
            elif op == 'APPEND':
                need(2)
                if type(stack[-2]) is not list:raise ValueError('APPEND requires a literal list')
                item = stack.pop();stack[-1].append(item)
            elif op == 'APPENDS':
                values = marked();need(1)
                if type(stack[-1]) is not list:raise ValueError('APPENDS requires a literal list')
                stack[-1].extend(values)
            elif op == 'SETITEM':
                need(3)
                if type(stack[-3]) is not dict:raise ValueError('SETITEM requires a literal dictionary')
                item = stack.pop();key = stack.pop();stack[-1][key] = item
            elif op == 'SETITEMS':
                values = marked();need(1)
                if type(stack[-1]) is not dict:raise ValueError('SETITEMS requires a literal dictionary')
                stack[-1].update(zip(values[::2], values[1::2], strict=True))
            elif op == 'MEMOIZE':
                need(1)
                index=len(memo)
                if index in memo:raise ValueError('Serialization memo slot reuse is unsupported')
                memo[index] = stack[-1]
            elif op in {'BINPUT', 'LONG_BINPUT', 'PUT'}:
                need(1)
                if not isinstance(value,(int,str)) or not 0 <= int(value) < 40_000_000:raise ValueError('Memo identity exceeds its bound')
                index=int(value)
                if index in memo:raise ValueError('Serialization memo slot reuse is unsupported')
                memo[index] = stack[-1]
            elif op in {'BINGET', 'LONG_BINGET', 'GET'}:
                if not isinstance(value,(int,str)) or not 0 <= int(value) < 40_000_000:raise ValueError('Memo reference exceeds its bound')
                target = memo[int(value)]
                if shared_ids is not None and isinstance(target, (list, dict, tuple, bytearray, Node)):
                    shared_ids.setdefault(id(target), int(value))
                stack.append(target)
            elif op in {'GLOBAL', 'STACK_GLOBAL'}:
                if op == 'GLOBAL':
                    if not isinstance(value,str):raise ValueError('Invalid global symbol operand')
                    module, name = value.split(' ', 1)
                else:
                    need(2);name, module = stack.pop(), stack.pop()
                symbol = Symbol(module, name);symbols.add(module + '.' + name);stack.append(symbol)
            elif op in {'REDUCE', 'NEWOBJ'}:
                need(2);args, symbol = stack.pop(), stack.pop()
                if type(args) is not tuple:raise ValueError('Neutral constructor requires tuple arguments')
                stack.append(Node(symbol, args, op))
            elif op == 'BUILD':
                need(2);state = stack.pop()
                if not isinstance(stack[-1], Node):raise ValueError('Neutral BUILD needs a neutral node')
                stack[-1].state = state
            elif op == 'POP':
                need(1);stack.pop()
            elif op == 'POP_MARK':marked()
            elif op == 'DUP':
                need(1);stack.append(stack[-1])
            elif op == 'STOP':
                guard()
                if len(stack) != 1 or stack[0] is mark or stream.read(1):raise ValueError('Invalid neutral serialization terminator')
                return stack[0], {'opcodes': ops, 'decoded_bytes': stream.total, 'symbols': sorted(symbols), 'memo_entries': len(memo)}
            else:raise ValueError('Unsupported serialization opcode: ' + op)
            if len(stack) > 100000 or len(memo) > 40_000_000:
                raise ValueError('Neutral serialization stack/memo exceeds bounds')
    raise ValueError('Missing serialization STOP')
