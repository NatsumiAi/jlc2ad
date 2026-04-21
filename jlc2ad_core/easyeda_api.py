from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class EasyEDAClient:
    VERSION = "6.4.19.5"
    COMPONENT_URL = f"https://easyeda.com/api/products/{{}}/components?version={VERSION}"
    PRO_PRODUCT_SEARCH_URL = "https://pro.easyeda.com/api/v2/eda/product/search"
    PRO_DEVICE_SEARCH_URL = "https://pro.easyeda.com/api/v2/devices/search"
    MODEL_STEP_URL = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"
    MODEL_OBJ_URL = "https://modules.easyeda.com/3dmodel/{uuid}"

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br',
        })
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def fetch(self, lcsc_id: str) -> dict:
        lcsc_id = self._normalize_lcsc_id(lcsc_id)

        component_result = self._fetch_component_result(lcsc_id)
        if not component_result:
            raise ValueError(f"Component {lcsc_id} not found")

        pkg = component_result.get('packageDetail') or self._find_nested_mapping(component_result, 'packageDetail')
        if not pkg:
            raise ValueError(f"Component {lcsc_id} has no footprint data")

        sch_data = component_result.get('dataStr') or self._find_nested_mapping(component_result, 'dataStr') or {}
        base_c_para = self._extract_c_para(sch_data, component_result)
        search_info = self._search_product_info(lcsc_id)

        device_info = search_info.get('device_info', {}) if search_info else {}
        device_attributes = self._extract_device_attributes(device_info)
        merged_attributes = dict(base_c_para)
        merged_attributes.update({k: v for k, v in device_attributes.items() if v not in (None, '', '-')})

        title = self._first_text(
            search_info.get('mpn') if search_info else None,
            merged_attributes.get('Manufacturer Part'),
            merged_attributes.get('Manufacturer Part Number'),
            component_result.get('title'),
            lcsc_id,
        )
        description = self._first_text(
            device_info.get('Description') if isinstance(device_info, dict) else None,
            search_info.get('description') if search_info else None,
            component_result.get('description'),
            merged_attributes.get('Description'),
            title,
        )
        manufacturer = self._first_text(
            merged_attributes.get('Manufacturer'),
            merged_attributes.get('Mf'),
            merged_attributes.get('Brand'),
        )
        supplier_part = self._first_text(
            search_info.get('number') if search_info else None,
            merged_attributes.get('Supplier Part'),
            merged_attributes.get('LCSC Part'),
            merged_attributes.get('LCSC Part #'),
            lcsc_id,
        )
        package_name = self._first_text(
            pkg.get('title') if isinstance(pkg, dict) else None,
            merged_attributes.get('package'),
            merged_attributes.get('Package'),
            lcsc_id,
        )
        model_3d = self._extract_3d_model(merged_attributes, device_info)

        return {
            'lcsc_id': lcsc_id,
            'title': title,
            'description': description,
            'value': self._first_text(merged_attributes.get('Value'), merged_attributes.get('value')),
            'manufacturer': manufacturer,
            'package_name': package_name,
            'package': self._first_text(merged_attributes.get('package'), merged_attributes.get('Package'), package_name),
            'manufacturer_part': self._first_text(
                merged_attributes.get('Manufacturer Part'),
                merged_attributes.get('Manufacturer Part Number'),
                search_info.get('mpn') if search_info else None,
                title,
            ),
            'supplier_part': supplier_part,
            'supplier': self._first_text(merged_attributes.get('Supplier'), 'LCSC'),
            'datasheet': self._first_text(
                merged_attributes.get('Datasheet'),
                merged_attributes.get('DataSheet'),
                device_info.get('datasheet') if isinstance(device_info, dict) else None,
                component_result.get('datasheetUrl'),
            ),
            'attributes': merged_attributes,
            'package_detail': pkg,
            'dataStr': pkg,
            'sch_dataStr': sch_data,
            'designator': self._first_text(merged_attributes.get('pre'), self._guess_designator(title, description)),
            'model_3d': model_3d,
        }

    def _fetch_component_result(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        try:
            payload = self._request_json('GET', self.COMPONENT_URL.format(lcsc_id))
        except Exception:
            payload = None
        if payload and payload.get('success') and isinstance(payload.get('result'), dict):
            return payload['result']
        return self._fetch_component_from_search(lcsc_id)

    def _fetch_component_from_search(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        product = self._search_product_info(lcsc_id)
        if not product:
            return None
        number = product.get('number') or product.get('lcsc_id') or lcsc_id
        try:
            payload = self._request_json('GET', self.COMPONENT_URL.format(self._normalize_lcsc_id(str(number))))
        except Exception:
            return None
        if payload.get('success') and isinstance(payload.get('result'), dict):
            return payload['result']
        return None

    def _search_product_info(self, lcsc_id: str) -> Dict[str, Any]:
        product = self._search_product(lcsc_id) or {}
        info = dict(product)
        mpn = self._first_text(info.get('mpn'), info.get('title'), info.get('name'))
        uid = self._first_text(info.get('uuid'), info.get('uid'), info.get('component_uuid'), info.get('number'), lcsc_id)
        if mpn and uid:
            device_info = self._search_device_info(mpn, uid)
            if device_info:
                info['device_info'] = device_info
        return info

    def _search_product(self, lcsc_id: str) -> Optional[Dict[str, Any]]:
        payload = {'codes': lcsc_id}
        headers = {
            'Referer': 'https://pro.easyeda.com/editor',
            'Origin': 'https://pro.easyeda.com',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        try:
            response = self._request_json('POST', self.PRO_PRODUCT_SEARCH_URL, json=payload, headers=headers)
        except Exception:
            return None
        products = response.get('result', {}).get('productList', [])
        normalized = lcsc_id.upper()
        for product in products:
            if not isinstance(product, dict):
                continue
            number = str(product.get('number', '')).strip().upper()
            if number == normalized:
                return product
        return products[0] if products and isinstance(products[0], dict) else None

    def _search_device_info(self, search: str, uid: str) -> Optional[Dict[str, Any]]:
        headers = {
            'Referer': 'https://pro.easyeda.com/editor',
            'Origin': 'https://pro.easyeda.com',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        form = {
            'page': '1',
            'pageSize': '1',
            'uid': uid,
            'path': uid,
            'wd': search.lower(),
            'returnListStyle': 'classifyarr',
        }
        try:
            response = self._request_json('POST', self.PRO_DEVICE_SEARCH_URL, data=form, headers=headers)
        except Exception:
            return None
        lcsc_items = response.get('result', {}).get('lists', {}).get('lcsc', [])
        if lcsc_items and isinstance(lcsc_items[0], dict):
            return lcsc_items[0]
        return None

    def _request_json(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected API payload from {url}")
        return payload

    def download_3d_step(self, model_uuid: str, destination: str) -> str:
        return self._download_binary(self.MODEL_STEP_URL.format(uuid=model_uuid), destination)

    def download_3d_obj(self, model_uuid: str, destination: str) -> str:
        return self._download_binary(self.MODEL_OBJ_URL.format(uuid=model_uuid), destination)

    def fetch_3d_obj_text(self, model_uuid: str) -> str:
        response = self.session.get(self.MODEL_OBJ_URL.format(uuid=model_uuid), timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _download_binary(self, url: str, destination: str) -> str:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        last_error = None
        for _ in range(3):
            try:
                with self.session.get(url, timeout=self.timeout, stream=True) as response:
                    response.raise_for_status()
                    with open(destination, 'wb') as file:
                        for chunk in response.iter_content(chunk_size=65536):
                            if chunk:
                                file.write(chunk)
                return destination
            except Exception as exc:
                last_error = exc
        raise last_error

    @staticmethod
    def _extract_c_para(*sources: Any) -> Dict[str, Any]:
        for source in sources:
            if not isinstance(source, dict):
                continue
            head = source.get('head')
            if isinstance(head, dict) and isinstance(head.get('c_para'), dict):
                return head['c_para']
            if isinstance(source.get('c_para'), dict):
                return source['c_para']
        return {}

    @staticmethod
    def _extract_device_attributes(device_info: Dict[str, Any]) -> Dict[str, Any]:
        attributes = device_info.get('attributes') if isinstance(device_info, dict) else None
        if isinstance(attributes, dict):
            return attributes
        return {}

    @staticmethod
    def _find_nested_mapping(root: Any, target_key: str) -> Optional[Dict[str, Any]]:
        if isinstance(root, dict):
            value = root.get(target_key)
            if isinstance(value, dict):
                return value
            for nested in root.values():
                found = EasyEDAClient._find_nested_mapping(nested, target_key)
                if found:
                    return found
        elif isinstance(root, list):
            for item in root:
                found = EasyEDAClient._find_nested_mapping(item, target_key)
                if found:
                    return found
        return None

    @staticmethod
    def _extract_3d_model(attributes: Dict[str, Any], device_info: Dict[str, Any]) -> Dict[str, Any]:
        model: Dict[str, Any] = {}
        for key in ('3D Model', '3D Model Name', '3D Model UUID', '3D Model Path', '3D Model Title'):
            value = attributes.get(key)
            if value:
                model[key] = value

        footprint_info = device_info.get('footprint_info') if isinstance(device_info, dict) else None
        if isinstance(footprint_info, dict):
            model_info = footprint_info.get('model_3d')
            if isinstance(model_info, dict):
                model.update(model_info)

        transform = attributes.get('3D Model Transform') or attributes.get('3D Model Transform Data')
        if isinstance(transform, str) and transform.strip():
            raw = transform.strip()
            model['transform_raw'] = raw
            parsed = EasyEDAClient._parse_transform_text(raw)
            if parsed:
                model['transform'] = parsed
        return model

    @staticmethod
    def _parse_transform_text(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        values = []
        for token in raw.replace(';', ',').split(','):
            token = token.strip()
            if not token:
                continue
            try:
                values.append(float(token))
            except ValueError:
                values = []
                break

        if len(values) >= 9:
            return {
                'size': {'x': values[0], 'y': values[1], 'z': values[2]},
                'rotation': {'x': values[3], 'y': values[4], 'z': values[5]},
                'offset': {'x': values[6], 'y': values[7], 'z': values[8]},
            }

        result: Dict[str, Any] = {}
        for part in raw.replace(';', ',').split(','):
            if ':' not in part:
                continue
            key, value = part.split(':', 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            try:
                result[key] = float(value)
            except ValueError:
                result[key] = value
        return result

    @staticmethod
    def _normalize_lcsc_id(lcsc_id: str) -> str:
        value = lcsc_id.strip().upper()
        if not value.startswith('C'):
            value = 'C' + value
        return value

    @staticmethod
    def _first_text(*values: Any) -> str:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text and text != '-':
                return text
        return ''

    @staticmethod
    def _guess_designator(title: str, desc: str) -> str:
        text = (title + ' ' + desc).lower()
        for keys, prefix in [
            (('capacitor', '电容', 'cap'), 'C?'),
            (('resistor', '电阻', 'res'), 'R?'),
            (('inductor', '电感', 'ind'), 'L?'),
            (('diode', '二极管'), 'D?'),
            (('transistor', '三极管', 'mosfet', 'bjt'), 'Q?'),
            (('led',), 'LED?'),
            (('connector', '连接器', 'header'), 'J?'),
            (('crystal', '晶振', 'oscillator'), 'Y?'),
        ]:
            if any(key in text for key in keys):
                return prefix
        return 'U?'


__all__ = ["EasyEDAClient"]
