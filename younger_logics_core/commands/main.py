#!/usr/bin/env python3
# -*- encoding=utf8 -*-

########################################################################
# Created time: 2024-12-11 14:30:52
# Author: Jason Young (杨郑鑫).
# E-Mail: AI.Jason.Young@outlook.com
# Last Modified by: Jason Young (杨郑鑫)
# Last Modified time: 2024-12-24 14:22:05
# Copyright (c) 2024 Yangs.AI
# 
# This source code is licensed under the Apache License 2.0 found in the
# LICENSE file in the root directory of this source tree.
########################################################################


import click

from younger_logics_core.commands.create import create
from younger_logics_core.commands.update import update
from younger_logics_core.commands.output import output


@click.group(name='younger-logics-core')
def main():
    pass


main.add_command(create, name='create')
main.add_command(update, name='update')
main.add_command(output, name='output')


if __name__ == '__main__':
    main()
