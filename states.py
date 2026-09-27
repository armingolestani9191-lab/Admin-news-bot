user_states = {}


def _key(user_id):
    return str(user_id)


def set_state(user_id, state, data=None):
    user_states[_key(user_id)] = {
        "state": state,
        "data": data or {},
    }


def get_state(user_id):
    return user_states.get(
        _key(user_id),
        {
            "state": None,
            "data": {},
        },
    )


def clear_state(user_id):
    user_states.pop(_key(user_id), None)
