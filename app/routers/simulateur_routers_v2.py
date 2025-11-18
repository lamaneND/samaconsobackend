# simulateur_router_v2.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
from pathlib import Path
from datetime import datetime
import random
import json
import xmltodict
import os
from typing import Optional
from xml.etree import ElementTree as ET
import urllib3
import tempfile

# ──────────────────────────────────────────────────────────────────────────────
# 0) Contournement OpenSSL (faible "CA_MD_TOO_WEAK") — doit être fait AVANT import ssl/requests
#    On crée un fichier de conf OpenSSL local et on pointe OPENSSL_CONF dessus.
#    Activez/désactivez via l'env LEGACY_TLS (par défaut: on).
# ──────────────────────────────────────────────────────────────────────────────
LEGACY_TLS = (os.getenv("LEGACY_TLS", "1") in ("1", "true", "TRUE", "yes", "YES"))

if LEGACY_TLS:
    try:
        _cnf_path = Path(tempfile.gettempdir()) / "openssl_legacy.cnf"
        if not _cnf_path.exists():
            _cnf_path.write_text(
                "openssl_conf = default_conf\n"
                "[default_conf]\n"
                "ssl_conf = ssl_sect\n"
                "[ssl_sect]\n"
                "system_default = system_default_sect\n"
                "[system_default_sect]\n"
                "CipherString = DEFAULT:@SECLEVEL=0\n"
                "MinProtocol = TLSv1.2\n"
            )
        # IMPORTANT : définir la variable d'environnement AVANT import ssl/requests_pkcs12
        os.environ["OPENSSL_CONF"] = str(_cnf_path)
    except Exception as _e:
        # on log, mais on n'empêche pas l'app de démarrer
        print(f"[WARN] Could not prepare OpenSSL legacy config: {_e}")

# ──────────────────────────────────────────────────────────────────────────────
# 1) Imports qui déclenchent le chargement OpenSSL => après OPENSSL_CONF
# ──────────────────────────────────────────────────────────────────────────────
import requests_pkcs12  # après OPENSSL_CONF pour prendre la conf en compte

# ──────────────────────────────────────────────────────────────────────────────
# Configuration logging & warnings
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ──────────────────────────────────────────────────────────────────────────────
# APIRouter
# ──────────────────────────────────────────────────────────────────────────────
simulateur_router_v2 = APIRouter(prefix="/simulateur", tags=["simulateur"])

# ──────────────────────────────────────────────────────────────────────────────
# SOAP / Cert configuration (identiques à ton fichier)
# ──────────────────────────────────────────────────────────────────────────────
SOAP_WSDL_URL = "https://10.101.1.160:8443/xmlvend/xmlvend.wsdl"
SOAP_SERVICE_NAME = "TrialCreditVendRequest"  # pour le header SOAPAction

CERTIFICATE_DIR = Path(__file__).parent  # même dossier que ce fichier
CERTIFICATE_PATH = CERTIFICATE_DIR / "414.pfx"
CERTIFICATE_PASSWORD = "9!!8..VaMeG8"

# ──────────────────────────────────────────────────────────────────────────────
# Modèles Pydantic
# ──────────────────────────────────────────────────────────────────────────────
class TrialCreditVendRequest(BaseModel):
    meter_no: str
    amount: float

class TrialCreditVendResponse(BaseModel):
    success: bool
    response: str
    date_time: str
    unique_number: str
    meter_no: str
    amount: float
    http_status: int = None
    error: str = None

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def generate_datetime() -> str:
    """YYYYMMDDHHMM"""
    return datetime.now().strftime("%Y%m%d%H%M")

def generate_unique_number() -> str:
    return str(random.randint(10000, 99999))

def create_soap_request(meter_no: str, amount: float, date_time: str, unique_number: str) -> str:
    """Construit la requête SOAP (structure conservée)"""
    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Body>
      <ns2:trialCreditVendReq xmlns:ns2="http://www.nrs.eskom.co.za/xmlvend/revenue/2.1/schema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns2:TrialCreditVendReq">
         <clientID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="EANDeviceID" ean="0000000000414"/>
         <terminalID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="GenericDeviceID" id="0000000000414"/>
         <msgID xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" dateTime="{date_time}" uniqueNumber="{unique_number}"/>
          <authCred xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema">
                <opName>AG0588</opName>
                <password>Senelec@123</password>
         </authCred>
         <resource xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="Electricity"/>
         <idMethod xmlns="http://www.nrs.eskom.co.za/xmlvend/base/2.1/schema" xsi:type="VendIDMethod">
            <meterIdentifier xsi:type="MeterNumber" msno="{meter_no}"/>
         </idMethod>
         <ns2:purchaseValue xsi:type="ns2:PurchaseValueCurrency">
            <ns2:amt value="{int(amount)}" symbol="AZM"/>
         </ns2:purchaseValue>
      </ns2:trialCreditVendReq>
   </soapenv:Body>
</soapenv:Envelope>"""

def _extract_endpoint_from_wsdl(wsdl_xml: str) -> Optional[str]:
    """Extrait soap:address/@location du WSDL, sinon None."""
    try:
        ns = {
            "wsdl": "http://schemas.xmlsoap.org/wsdl/",
            "soap": "http://schemas.xmlsoap.org/wsdl/soap/",
            "soap12": "http://schemas.xmlsoap.org/wsdl/soap12/",
        }
        root = ET.fromstring(wsdl_xml)
        for addr in root.findall(".//wsdl:service/wsdl:port/soap:address", ns):
            loc = addr.get("location")
            if loc:
                return loc
        for addr in root.findall(".//wsdl:service/wsdl:port/soap12:address", ns):
            loc = addr.get("location")
            if loc:
                return loc
    except Exception as e:
        logger.warning(f"Could not parse WSDL for endpoint: {e}")
    return None

def parse_soap_response(xml_content: str, request_date_time: str, unique_number: str, http_status: int) -> dict:
    """Parsing identique à ta version précédente → JSON structuré."""
    try:
        parsed_xml = xmltodict.parse(xml_content)
        body = parsed_xml["SOAP-ENV:Envelope"]["SOAP-ENV:Body"]["ns3:trialCreditVendResp"]

        json_result = {
            "success": http_status == 200,
            "http_status": http_status,
            "error": None,
            "device_info": {
                "client_id": {
                    "ean": body.get("ns2:clientID", {}).get("@ean"),
                    "type": body.get("ns2:clientID", {}).get("@xsi:type")
                },
                "server_id": {
                    "ean": body.get("ns2:serverID", {}).get("@ean"),
                    "type": body.get("ns2:serverID", {}).get("@xsi:type")
                },
                "terminal_id": {
                    "id": body.get("ns2:terminalID", {}).get("@id"),
                    "type": body.get("ns2:terminalID", {}).get("@xsi:type")
                }
            },
            "transaction_info": {
                "response_date_time": body["ns2:respDateTime"],
                "request_date_time": request_date_time,
                "unique_number": unique_number,
                "receipt_no": body["ns3:creditVendReceipt"]["@receiptNo"],
                "display_header": body.get("ns2:dispHeader")
            },
            "utility": {
                "name": body.get("ns2:utility", {}).get("@name"),
                "address": body.get("ns2:utility", {}).get("@address")
            },
            "vendor": {
                "name": body.get("ns2:vendor", {}).get("@name"),
                "address": body.get("ns2:vendor", {}).get("@address")
            },
            "client": {
                "account_no": body["ns2:custVendDetail"]["@accNo"],
                "name": body["ns2:custVendDetail"]["@name"].strip(),
                "address": body["ns2:custVendDetail"]["@address"],
                "location_ref": body["ns2:custVendDetail"]["@locRef"],
                "days_since_last_purchase": int(body["ns2:custVendDetail"]["@daysLastPurchase"]),
                "available_credit": {
                    "currency": body["ns2:clientStatus"]["ns2:availCredit"]["@symbol"],
                    "value": float(body["ns2:clientStatus"]["ns2:availCredit"]["@value"])
                }
            }
        }

        tx_list = body["ns3:creditVendReceipt"]["ns3:transactions"]["ns3:tx"]
        if isinstance(tx_list, dict):
            tx_list = [tx_list]

        credit_tx = next((tx for tx in tx_list if "CreditVendTx" in tx["@xsi:type"]), None)
        debt_recovery_tx = next((tx for tx in tx_list if "DebtRecoveryTx" in tx["@xsi:type"]), None)
        service_charges = [tx for tx in tx_list if "ServiceChrgTx" in tx["@xsi:type"]]

        if credit_tx:
            meter_detail = credit_tx["ns3:creditTokenIssue"]["ns2:meterDetail"]
            json_result["meter"] = {
                "number": meter_detail["@msno"],
                "sgc": meter_detail["@sgc"],
                "krn": meter_detail["@krn"],
                "ti": meter_detail["@ti"],
                "meter_type": {
                    "at": meter_detail.get("ns2:meterType", {}).get("@at"),
                    "tt": meter_detail.get("ns2:meterType", {}).get("@tt")
                },
                "max_vend_amount": float(meter_detail["ns2:maxVendAmt"]),
                "min_vend_amount": float(meter_detail["ns2:minVendAmt"]),
                "max_vend_energy": float(meter_detail["ns2:maxVendEng"]),
                "min_vend_energy": float(meter_detail["ns2:minVendEng"])
            }

            units = credit_tx["ns3:creditTokenIssue"]["ns2:units"]
            json_result["purchase"] = {
                "receipt_no": credit_tx.get("@receiptNo"),
                "amount": {
                    "value": float(credit_tx["ns3:amt"]["@value"]),
                    "currency": credit_tx["ns3:amt"]["@symbol"]
                },
                "units": {
                    "value": float(units["@value"]),
                    "unit": units["@siUnit"]
                },
                "tariff": {
                    "name": credit_tx.get("ns3:tariff", {}).get("ns2:name")
                },
                "resource_type": credit_tx["ns3:creditTokenIssue"].get("ns2:resource", {}).get("@xsi:type")
            }

            token_issue = credit_tx["ns3:creditTokenIssue"]
            if "ns2:token" in token_issue:
                token = token_issue["ns2:token"]
                json_result["token"] = {
                    "type": token.get("@xsi:type"),
                    "sts_cipher": token.get("ns2:stsCipher", ""),
                    "description": token_issue.get("ns2:desc")
                }

            if "ns3:creditStep" in credit_tx:
                json_result["credit_steps"] = []
                steps = credit_tx["ns3:creditStep"]["ns3:creditStepTx"]
                if isinstance(steps, dict):
                    steps = [steps]
                for step in steps:
                    step_end_value = step.get("ns2:stepE")
                    step_end = None if not step_end_value or step_end_value == "" else int(step_end_value)
                    step_begin_value = step.get("ns2:stepB", 0)
                    step_begin = 0 if not step_begin_value or step_begin_value == "" else int(step_begin_value)

                    json_result["credit_steps"].append({
                        "step_begin": step_begin,
                        "step_end": step_end,
                        "price_per_unit": float(step.get("ns2:price", 0)),
                        "amount": {
                            "value": float(step.get("ns2:amt", {}).get("@value", 0)),
                            "currency": step.get("ns2:amt", {}).get("@symbol")
                        },
                        "units": {
                            "value": float(step.get("ns2:units", {}).get("@value", 0)),
                            "unit": step.get("ns2:units", {}).get("@siUnit")
                        }
                    })

        if debt_recovery_tx:
            json_result["debt_recovery"] = {
                "account_no": debt_recovery_tx.get("ns3:accNo"),
                "description": debt_recovery_tx.get("ns3:accDesc"),
                "amount": {
                    "value": float(debt_recovery_tx["ns3:amt"]["@value"]),
                    "currency": debt_recovery_tx["ns3:amt"]["@symbol"]
                },
                "balance": {
                    "value": float(debt_recovery_tx.get("ns3:balance", {}).get("@value", 0)),
                    "currency": debt_recovery_tx.get("ns3:balance", {}).get("@symbol")
                },
                "tariff": {
                    "name": debt_recovery_tx.get("ns3:tariff", {}).get("ns2:name")
                }
            }

        json_result["service_charges"] = []
        for tx in service_charges:
            json_result["service_charges"].append({
                "type": "ServiceCharge",
                "account_no": tx.get("ns3:accNo"),
                "description": tx.get("ns3:accDesc"),
                "amount": {
                    "value": float(tx["ns3:amt"]["@value"]),
                    "currency": tx["ns3:amt"]["@symbol"]
                },
                "tariff": {
                    "name": tx.get("ns3:tariff", {}).get("ns2:name")
                }
            })

        transactions = body["ns3:creditVendReceipt"]["ns3:transactions"]
        json_result["transaction_totals"] = {
            "less_round": {
                "value": float(transactions.get("ns3:lessRound", {}).get("@value", 0)),
                "currency": transactions.get("ns3:lessRound", {}).get("@symbol")
            },
            "tender_amount": {
                "value": float(transactions.get("ns3:tenderAmt", {}).get("@value", 0)),
                "currency": transactions.get("ns3:tenderAmt", {}).get("@symbol")
            },
            "change": {
                "value": float(transactions.get("ns3:change", {}).get("@value", 0)),
                "currency": transactions.get("ns3:change", {}).get("@symbol")
            }
        }

        return json_result

    except Exception as e:
        logger.error(f"Error parsing SOAP response: {e}", exc_info=True)
        return {
            "success": False,
            "http_status": http_status,
            "error": f"Failed to parse XML response: {str(e)}",
            "raw_response": xml_content
        }

# ──────────────────────────────────────────────────────────────────────────────
# Endpoint principal — 100% requests-pkcs12
# ──────────────────────────────────────────────────────────────────────────────
@simulateur_router_v2.post("/trial-credit-vend-request")
async def trial_credit_vend_request(request: TrialCreditVendRequest):
    """
    Appelle TrialCreditVendRequest (SOAP) avec certificat client PFX.
    - meter_no: numéro de compteur
    - amount: montant
    """
    try:
        if not CERTIFICATE_PATH.exists():
            raise FileNotFoundError(f"Client certificate not found: {CERTIFICATE_PATH}")

        date_time = generate_datetime()
        unique_number = generate_unique_number()

        # 1) GET WSDL via PFX (même logique que SoapUI)
        logger.info(f"Fetching WSDL with PFX: {SOAP_WSDL_URL}")
        wsdl_resp = requests_pkcs12.get(
            SOAP_WSDL_URL,
            pkcs12_filename=str(CERTIFICATE_PATH),
            pkcs12_password=CERTIFICATE_PASSWORD,
            timeout=30,
            verify=False  # aligné avec ton implémentation initiale
        )
        wsdl_resp.raise_for_status()

        # 2) Endpoint depuis le WSDL ou fallback
        endpoint_url = _extract_endpoint_from_wsdl(wsdl_resp.text) or SOAP_WSDL_URL.replace(".wsdl", "")
        logger.info(f"Using SOAP endpoint: {endpoint_url}")

        # 3) Payload SOAP
        soap_xml = create_soap_request(
            meter_no=request.meter_no,
            amount=request.amount,
            date_time=date_time,
            unique_number=unique_number
        )

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": SOAP_SERVICE_NAME,
            "Accept": "text/xml",
        }

        # 4) POST SOAP via PFX direct
        response = requests_pkcs12.post(
            endpoint_url,
            data=soap_xml,
            headers=headers,
            timeout=60,
            verify=False,  # idem
            pkcs12_filename=str(CERTIFICATE_PATH),
            pkcs12_password=CERTIFICATE_PASSWORD,
        )

        parsed = parse_soap_response(
            xml_content=response.text,
            request_date_time=date_time,
            unique_number=unique_number,
            http_status=response.status_code
        )
        return parsed

    except Exception as e:
        logger.error(f"Error in TrialCreditVendRequest: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "certificate_path": str(CERTIFICATE_PATH),
                "certificate_exists": CERTIFICATE_PATH.exists()
            }
        )

# ──────────────────────────────────────────────────────────────────────────────
# Endpoints utilitaires
# ──────────────────────────────────────────────────────────────────────────────
@simulateur_router_v2.get("/")
async def root():
    return {
        "message": "TrialCreditVendRequest SOAP Client API",
        "endpoints": {
            "main": "/trial-credit-vend-request",
            "docs": "/docs"
        },
        "certificate_path": str(CERTIFICATE_PATH),
        "certificate_exists": CERTIFICATE_PATH.exists(),
        "legacy_tls": LEGACY_TLS,
        "openssl_conf": os.environ.get("OPENSSL_CONF")
    }

@simulateur_router_v2.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "certificate_configured": CERTIFICATE_PATH.exists(),
        "certificate_path": str(CERTIFICATE_PATH),
        "legacy_tls": LEGACY_TLS
    }
