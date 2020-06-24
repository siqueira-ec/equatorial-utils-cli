#!/usr/bin/env python3

import sys
import time
import threading

import requests as rq
import json
from base64 import b64decode

import click
import six

import questionary
from questionary import ValidationError, Validator, Choice
from prompt_toolkit.styles import Style

from pyfiglet import figlet_format

try:
    import colorama
    colorama.init()
except ImportError:
    colorama = None

try:
    from termcolor import colored
except ImportError:
    colored = None


class Spinner:
    busy = False
    delay = 0.1

    @staticmethod
    def spinning_cursor():
        while 1:
            for cursor in '|/-\\':
                yield cursor

    def __init__(self, delay=None):
        self.spinner_generator = self.spinning_cursor()
        if delay and float(delay):
            self.delay = delay

    def spinner_task(self):
        while self.busy:
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.busy = True
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.busy = False
        time.sleep(self.delay)
        if exception is not None:
            return False


# custom style for question properties
custom_style = Style([
    ('qmark', 'fg:#fac731 bold'),       # token in front of the question
    ('question', ''),               # question text
    # pointer used in select and checkbox prompts
    ('pointer', 'fg:#673ab7 bold'),
    # pointed-at choice in select and checkbox prompts
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#0abf5b'),         # style for a selected item of a checkbox
    ('separator', 'fg:#cc5454'),        # separator in lists
    # user instructions for select, rawselect, checkbox
    ('instruction', ''),
    ('text', 'fg:#4688f1 bold'),                       # plain text
    # disabled choices for select and checkbox prompts
    ('disabled', 'fg:#858585 italic'),
    # submitted answer text behind the question
    ('answer', 'fg:#f44336 bold'),
])

# api routes/endpoints
routes = {
    'auth': {
        'route': 'https://api-pa-cliente.equatorialenergia.com.br/auth/connect/token',
        'headers': {
            'Authorization': 'Basic  Y2VtYXI6RXF0QENlbWFy'
        },
        'body': {
            'grant_type': 'password',
            'username': '',
            'password': '',
            'navegador': 'browser',
            'dispositivo': 'device',
            'empresaId': '+'
        }
    },
    'bills': {
        'route': 'https://api-pa-cliente.equatorialenergia.com.br/api/v1/debitos/',
        'options': {
            'open_bills': '?listarEmAberto=true',
            'all_bills': '?listarEmAberto=false'
        }
    },
    'pdf': {
        'route': 'https://api-pa-cliente.equatorialenergia.com.br/api/v1/faturas/segunda-via/',
        'options': {
            'show_url': '?showUrl=true'
        }
    }
}


def getToken(username, password):
    """
    getToken - Get authentication bearer token.

    Get 'username' and 'password', request data on auth endpoint and return token object.

    Parameters:
        username (str): Username to login (cpf).
        password (str): Password of given username (born date).

    Returns:
        token (list): List object of token
    """
    # set request body
    body = routes['auth']['body'].copy()
    body['username'] = '1:' + username
    body['password'] = password

    # request on endpoint
    token_resp = rq.post(
        url=routes['auth']['route'],
        data=body,
        headers=routes['auth']['headers']
    )

    # parse response as json
    token = json.loads(token_resp.text)

    # return token list object
    return token


def extractUserDataFromToken(token):
    # get user data split in token
    encoded_user_data = token['access_token'].split('.')[1]

    # append tabulation
    encoded_user_data += "=" * ((4 - len(encoded_user_data) % 4) % 4)

    # decode user data
    decoded_user_data = b64decode(encoded_user_data)

    # parse user data as json
    json_user_data = json.loads(decoded_user_data)['userData']

    # return user data parsed as json
    return json_user_data


def getUcs(personal_data):
    cc = personal_data['ContasContrato']
    ucs = []
    for contrato in cc:
        Numero = contrato['Numero']
        Endereco = contrato['Endereco']
        Bairro = contrato['Bairro']
        Cidade = contrato['Cidade']

        ucs.append(
            {
                'numero': Numero,
                'endereco': Endereco + ', ' + Bairro + ', ' + Cidade
            }
        )

    return ucs


def getOpenBills(ucs):
    # get open bills
    open_bills = {}

    for uc in ucs:
        open_bills_resp = rq.get(
            url=routes['bills']['route'] + uc
        )

        content = open_bills_resp.text
        status = open_bills_resp.status_code
        headers = open_bills_resp.headers

        open_bills_data = json.loads(content)['data']['faturas'] if (
            status == 200 and 'application/json' in headers['Content-Type']) else 'Não há faturas em aberto para esta conta contrato.'
        open_bills[uc] = open_bills_data

    return open_bills


def getAllBills(uc):
    # get all bills
    all_bills_url = routes['bills']['route'] + \
        uc + routes['bills']['options']['all_bills']

    all_bills_text = rq.get(url=all_bills_url).text

    all_bills = json.loads(all_bills_text)

    return all_bills


def getBillPdf(bill_num, token):
    get_bill_pdf_url = routes['pdf']['route'] + bill_num + \
        routes['pdf']['route']['options']['show_url']

    get_bill_pdf_headers = {
        'Authorization': token['token_type'] + ' ' + token['access_token']
    }

    bill_text = rq.get(url=get_bill_pdf_url, headers=get_bill_pdf_headers).text

    bill = json.loads(bill_text)

    return bill


def saveBillPdf(bill_data, period, name='fatura_equatorial'):
    """
    saveBillPdf - Save bills as '.pdf' file.

    Get 'bill_data', transform in bytes and save it as pdf with 'name' + month|year based on 'period'.
    i.e: saveBillPdf(bill_data, period='04/2020', name='bill_test') will generate a file named 'bill_test - 04/2020.pdf'

    Parameters:
        bill_data (list): List object describing bill.
        period (str): Bill period.
        name (str): Desired filename.
    """
    # encode bill_data as bytes
    bytes = b64decode(bill_data['data']['base64'], validate=True)

    # get month and year vars for file naming
    year, month = period.split('/')

    # set path str to save file
    path = '{n} - {m}|{y}.pdf'.format(n=name, m=month, y=year)

    # try to save file
    try:
        f = open(path, 'wb')
        f.write(bytes)
        f.close()
        print('Arquivo {path} salvo com sucesso!'.format(path=path))
    except Exception as e:
        raise(e)


def log(string, color, font="slant", figlet=False):
    if colored:
        if not figlet:
            six.print_(colored(string, color))
        else:
            six.print_(colored(figlet_format(
                string, font=font), color))
    else:
        six.print_(string)


class EmptyValidator(Validator):
    def validate(self, value):
        if len(value.text):
            return True
        else:
            raise ValidationError(
                message="Esse campo é de preenchimento obrigatório.",
                cursor_position=len(value.text))


def askUcs(personal_data):

    ucs = getUcs(personal_data)

    uc_choices = []

    selected = []

    for uc in ucs:
        uc_choices.append(
            Choice(
                title='{num} - {end}'.format(num=uc['numero'],
                                             end=uc['endereco']),
                value=uc['numero']
            )
        )

    uc_choices.append(
        Choice(
            title='Todos os contratos',
            value='all'
        )
    )

    selected_uc = questionary.select(
        message='Selecione um contrato para emissão de faturas pendentes:',
        choices=uc_choices,
        style=custom_style
    ).ask()

    # selected all ucs
    if selected_uc == 'all':
        for choice in uc_choices:
            selected.append(choice.value)

        selected.pop()
    # selected single uc
    else:
        selected.append(selected_uc)

    return selected


def askPersonalData():
    cpf = questionary.text(
        message='Insira o CPF do titular',
        validate=EmptyValidator,
        style=custom_style
    ).ask()

    born_date = questionary.text(
        message='Insira a Data de Nascimento do Titular (AAAA-MM-DD)',
        validate=EmptyValidator,
        style=custom_style
    ).ask()

    return cpf.strip(), born_date.strip()


def saveOpenBills(uc_bills_dict, token):
    for index in uc_bills_dict:
        if type(uc_bills_dict[index]) is list:
            for bill in uc_bills_dict[index]:
                bill_data = getBillPdf(bill['numeroFatura'], token)

                try:
                    saveBillPdf(
                        bill_data=bill_data,
                        period=bill['competencia'],
                        name='fatura_equatorial_{uc}'.format(uc=index)
                    )
                except Exception as e:
                    raise Exception(
                        "Ocorreu um erro ao salvar a fatura: %s" % (e))
        else:
            print('Sem faturas abertas para a uc {uc}!'.format(uc=index))


@click.command()
def main():
    """
    Cli básica para exibição/emissão de faturas da Equatorial Energia - Pará
    """

    log("Equatorial/PA CLI", color="blue", figlet=True)
    log("Bem Vindo ao Equatorial/PA CLI", "green")

    cpf, born_date = askPersonalData()
    token = []
    with Spinner():
        token = getToken(cpf, born_date)
    personal_data = extractUserDataFromToken(token)
    selected_uc = askUcs(personal_data)
    uc_bills_dict = {}
    with Spinner():
        uc_bills_dict = getOpenBills(selected_uc)

    try:
        with Spinner():
            saveOpenBills(uc_bills_dict, token)
    except Exception as e:
        raise(e)


if __name__ == '__main__':
    main()
