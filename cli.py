#!/usr/bin/env python3

import os
import re

import requests as rq
import json
from base64 import b64decode

import click
import six
from PyInquirer import (Token, ValidationError, Validator, print_json, prompt,
                        style_from_dict)

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

style = style_from_dict({
    Token.QuestionMark: '#fac731 bold',
    Token.Answer: '#4688f1 bold',
    Token.Instruction: '',  # default
    Token.Separator: '#cc5454',
    Token.Selected: '#0abf5b',  # default
    Token.Pointer: '#673ab7 bold',
    Token.Question: '',
})

def getContentType(answer, conttype):
    return answer.get("content_type").lower() == conttype.lower()

def getEquatorialToken(personalInfo):
    # get token
    token_req_url = 'https://api-pa-cliente.equatorialenergia.com.br/auth/connect/token'
    token_req_body = {
        'grant_type': 'password',
        'username': '1:' + personalInfo.get('cpf'),
        'password': personalInfo.get('born_date'),
        'navegador': 'browser',
        'dispositivo': 'device',
        'empresaId': '+'
    }
    token_req_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:75.0) Gecko/20100101 Firefox/75.0',
        'Authorization': 'Basic  Y2VtYXI6RXF0QENlbWFy'
    }
    token_text = rq.post(url=token_req_url, data=token_req_body, headers=token_req_headers).text
    token = json.loads(token_text)
    return token

def getOpenBills(personalInfo):
    # get open bills
    get_open_bills_url = 'https://api-pa-cliente.equatorialenergia.com.br/api/v1/faturas/em-aberto/' + personalInfo.get('uc')
    open_bills_text = rq.get(url=get_open_bills_url).text
    open_bills = json.loads(open_bills_text)
    return open_bills

def getAllBills(personalInfo):
    # get all bills
    get_all_bills_url = 'https://api-pa-cliente.equatorialenergia.com.br/api/v1/debitos/' + personalInfo.get('uc') + '?listarEmAberto=false'
    all_bills_text = rq.get(url=get_all_bills_url).text
    all_bills = json.loads(all_bills_text)
    return all_bills

def getBillPdf(bill_num, token):
    # get open bills pdf
    bill_get_pdf = 'https://api-pa-cliente.equatorialenergia.com.br/api/v1/faturas/segunda-via/' + bill_num + '?showUrl=true'
    headers_get_pdf = {
        'Authorization': token['token_type'] + ' ' + token['access_token']
    }
    bill_text = rq.get(url=bill_get_pdf, headers=headers_get_pdf).text
    bill = json.loads(bill_text)
    return bill

def saveBillPdf(personalInfo):
    # get vars
    token = getEquatorialToken(personalInfo)
    open_bills = getOpenBills(personalInfo)
    bill_pdf = getBillPdf(open_bills[0]['referenciaFatura'], token)
    # saves pdf bill on disk
    bytes = b64decode(bill_pdf['data']['base64'], validate=True)
    f = open('fatura_equatorial.pdf', 'wb')
    f.write(bytes)
    f.close()
    return True

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

def askPersonalData():

    questions = [
        {
            'type': 'input',
            'name': 'uc',
            'message': 'Unidade Consumidora',
            'validate': EmptyValidator
        },
        {
            'type': 'input',
            'name': 'cpf',
            'message': 'CPF do Titular',
            'validate': EmptyValidator
        },
        {
            'type': 'input',
            'name': 'born_date',
            'message': 'Data de Nascimento do Titular',
            'validate': EmptyValidator
        },
        {
            'type': 'confirm',
            'name': 'pdf',
            'message': 'Gostaria de Emitir o PDF?'
        }
    ]

    answers = prompt(questions, style=style)
    return answers

@click.command()
def main():
    """
    Simple CLI to emit and exibit bills from Equatorial
    """

    log("Equatorial CLI", color="blue", figlet=True)
    log("Bem Vindo ao Equatorial CLI", "green")

    personalInfo = askPersonalData()
    if personalInfo.get("pdf", False):
        try:
            response = saveBillPdf(personalInfo)
        except Exception as e:
            raise Exception("An error occured: %s" % (e))

        if response:
            log("Fatura salva com sucesso", "blue")
        else:
            log("Erro ao salvar fatura", "red")

if __name__ == '__main__':
    main()
