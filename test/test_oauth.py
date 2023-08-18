from server.auth import OAuthContext, serialize_auth_context, deserialize_auth_context

def test_auth_context_encoding():
    context = OAuthContext(state="foo", redirect_uri="bar")
    serialized = serialize_auth_context(context)
    # Note that JSON serialization isn't necessarily deterministic
    # so if this test is reliable, that's just our luck
    assert serialized == 'eyJzdGF0ZSI6ICJmb28iLCAicmVkaXJlY3RfdXJpIjogImJhciJ9'
    context2 = deserialize_auth_context(serialized)
    assert context == context2
