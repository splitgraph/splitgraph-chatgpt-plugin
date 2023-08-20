from server.auth import OAuthContext, serialize_auth_context, deserialize_auth_context, encode_jwt_token, decode_jwt_token

def test_auth_context_encoding():
    context = OAuthContext(state="foo", redirect_uri="bar")
    serialized = serialize_auth_context(context)
    # Note that JSON serialization isn't necessarily deterministic
    # so if this test is reliable, that's just our luck
    assert serialized == 'eyJzdGF0ZSI6ICJmb28iLCAicmVkaXJlY3RfdXJpIjogImJhciJ9'
    context2 = deserialize_auth_context(serialized)
    assert context == context2

def test_jwt_encoding():
    google_user_id='111'
    email="bob@test.com"
    aud="aud"
    secret="secret"
    token = encode_jwt_token(sub=google_user_id, email=email, grant='code', aud=aud, secret=secret)
    decoded_token = decode_jwt_token(token, aud=aud, secret=secret)
    assert decoded_token.sub == google_user_id
    assert decoded_token.email == email

