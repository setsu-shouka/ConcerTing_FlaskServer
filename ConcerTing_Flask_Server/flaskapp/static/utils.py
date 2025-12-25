# -*- coding: UTF-8 -*-
import requests

# Google Place API Key
google_Place_API_Key = 'AIzaSyDtonL9VSQAeScJ5KtLb60G3zPCc8XnWBs'
googleGeocodingRequest_Url = 'https://maps.googleapis.com/maps/api/geocode/json'
# Central Weather Bureau API Key
cwb_key = 'CWB-FE15BA9C-5740-4C5A-9793-31F0269E6747'


def get_locationName_from_address(address):
    googleMapRequest_params = dict(
        address=address,
        key=google_Place_API_Key,
        language="zh-TW"
    )
    place_json_data = requests.get(url=googleGeocodingRequest_Url, params=googleMapRequest_params).json()
    if not place_json_data['results']:
        return None
    else:
        locationName = {}
        for types in place_json_data['results'][0]['address_components']:
            if types['types'][0] == 'administrative_area_level_1':
                locationName['city'] = types['long_name']
            elif types['types'][0] == 'administrative_area_level_2':
                locationName['city'] = types['long_name']
            elif types['types'][0] == 'administrative_area_level_3':
                locationName['area'] = types['long_name']
        return locationName


def get_weather_info(data_id, area):
    cwb_api_url = 'https://opendata.cwb.gov.tw/api/v1/rest/datastore/' + data_id
    cwb_api_params = dict(
        locationName=area,
        authorizationkey=cwb_key
    )
    cwb_json_data = requests.get(url=cwb_api_url, params=cwb_api_params).json()
    weather_info = cwb_json_data['records']['locations'][0]['location'][0]['weatherElement']
    for types in weather_info:
        if types['description'] == '天氣預報綜合描述':
            time = types['time']
            return time
        else:
            continue
