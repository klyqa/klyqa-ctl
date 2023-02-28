from test.conftest import TEST_UNIT_ID

TEST_IP: str = "192.168.8.4"


DATA_IDENTITY: bytes = (
    b'\x00\xda\x00\x00{"type":"ident","ident":{"fw_version":"virtual","fw_build":"1","hw_version":"1","manufacturer_id":"59a58a9f-59ca-4c46-96fc-791a79839bc7","product_id":"@qcx.lighting.rgb-cw-ww.virtual","unit_id":"'
    + TEST_UNIT_ID.encode("utf-8")
    + b'"}}'
)
