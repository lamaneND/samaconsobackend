from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from zeep import Client

from app.schemas.user_schemas import UserSendSmsSchema

sms_router = APIRouter(prefix="/sms",tags=["sms"])

SOAP_WSDL_URL = "http://10.101.2.86:8080/OrangeSmsPro/OSPWebService?wsdl"



@sms_router.post("/sendsms/")
async def call_sms_service(smsParams: UserSendSmsSchema):
    try:
        # Create SOAP client
        client = Client(SOAP_WSDL_URL)

        # Call the SOAP method (replace 'YourSoapMethod' with the actual method name)
        response = client.service.sendOneSMS(smsParams.telephone, smsParams.message)
        r = str(response)

        response_data = eval(response)  # This is unsafe in production, consider JSON parsing
            
            # Extract status code and text
        responses = response_data.get("responses", {}).get("response", [])
        if responses:
                status = responses[0].get("status", {})
                status_code = status.get("status_CODE")
                status_text = status.get("status_TEXT")
        
        return {
            "response": r.replace('\\', ''),
            "status_code": status_code,
            "status_text": status_text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))