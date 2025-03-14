import sys
import uuid
import inspect
import threading

from awscrt     import mqtt
from awsiot     import iotshadow, mqtt_connection_builder

# Local
import sensorctl

from log        import log
from configs    import thing_config


#input_topic = f'$aws/things/{thing_config.thing_name}/shadow/update/delta'

received_all_event = threading.Event()

shadow_client = None

def on_update_shadow_accepted(response):
    log.info(f"Update shadow accepted:{response.state.desired}")
    functions = dict(inspect.getmembers(sensorctl, inspect.isfunction))
    for state, value in response.state.desired.items():
        print(f"State:{state} Value:{value}")
        if state in functions:
            try:
                if isinstance(value, list):
                    arg1 = value[0]
                    arg2 = value[1:]
                else:
                    arg1 = value
                    arg2 = None
                result = functions[state](arg1, arg2)
                log.info(f"Function:{functions[state]} Result:{result}")

            except Exception as e:
                log.error("Error:{} handling message in method {}".format(str(e), state))


def on_publish_update_shadow(future):
    log.info(f"Publish update shadow:{future}")
    try:
        future.result()
        log.info("Update request published.")
    except Exception as e:
        log.error("Failed to publish update request.")


def change_shadow_value(property, value):
    """

    :param property:
    :param value:
    :return:
    """
    global shadow_client
    token = str(uuid.uuid4())
    state = iotshadow.ShadowState(reported={property: value}, desired={property: value})

    request = iotshadow.UpdateShadowRequest(thing_name=thing_config.thing_name, client_token=token, state=state)
    future = shadow_client.publish_update_shadow(request, mqtt.QoS.AT_LEAST_ONCE)
    future.add_done_callback(on_publish_update_shadow)


def on_shadow_delta_updated(delta):
    """

     :param response:
     :return:
     """
    log.info(f"Delta updated:{delta.state}")
    functions = dict(inspect.getmembers(sensorctl, inspect.isfunction))
    for state, value in delta.state.items():
        if state in functions:
            try:
                if isinstance(delta.state[state], list):
                    arg1 = delta.state[state][0]
                    arg2 = delta.state[state][1:]
                else:
                    arg1 = delta.state[state]
                    arg2 = []
                result = functions[state](arg1, arg2)

            except Exception as e:
                log.error("Error:{} handling message in method {}".format(str(e), state))
            else:
                log.info(f"Function:{state} returned:{result}")
                change_shadow_value(state, delta.state[state])
        else:
            change_shadow_value(state, None)


# All of these functions are MQTT callbacks
def on_connection_interrupted(connection, error, **kwargs):
    """
    Callback when connection is accidentally lost
    :param connection:
    :param error:
    :param kwargs:
    :return:
    """
    log.info("Connection interrupted. error: {}".format(error))


def on_connection_resumed(connection, return_code, session_present, **kwargs):
    """
    Callback when an interrupted connection is re-established.
    :param connection:
    :param return_code:
    :param session_present:
    :param kwargs:
    :return:
    """
    log.info("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        log.info("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
    """
    Resubscribe to topic complete
    :param resubscribe_future:
    :return:
    """
    results = resubscribe_future.result()
    log.info(f"Resubscribe results: {results}")

    for topic, qos in results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))


def on_connection_success(connection, callback_data):
    """
    Callback when the connection successfully connects
    :param connection:
    :param callback_data:
    :return:
    """
    log.info(f"Connection Successful with return code:{callback_data.return_code} session present:{callback_data.session_present}")


def on_connection_failure(connection, callback_data):
    """
    Callback when a connection attempt fails
    :param connection:
    :param callback_data:
    :return:
    """
    log.error(f"Connection failed with error code: {callback_data.error}")


def on_connection_closed(connection, callback_data):
    """
    Callback when a connection has been disconnected or shutdown successfully
    :param connection:
    :param callback_data:
    :return:
    """
    log.info(f"Connection {connection} closed {callback_data}")


def shadow():
    global shadow_client

    # Create a MQTT connection from the command line data
    mqtt_connect = mqtt_connection_builder.mtls_from_path(
        endpoint=thing_config.endpoint,
        port=8883,
        cert_filepath=thing_config.cert,
        pri_key_filepath=thing_config.key,
        ca_filepath=thing_config.input_ca,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=str(uuid.uuid4()),
        clean_session=False,
        keep_alive_secs=30,
        on_connection_success=on_connection_success,
        on_connection_failure=on_connection_failure,
        on_connection_closed=on_connection_closed)

    connect_future = mqtt_connect.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    log.info("Connected!")

    shadow_client = iotshadow.IotShadowClient(mqtt_connect)

    try:
        update_accepted_subscribed_future, _ = shadow_client.subscribe_to_update_shadow_accepted(
            request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=thing_config.thing_name),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_update_shadow_accepted)
    except Exception as e:
        log.error(f"Error:{e} trying to set up update shadow accepted")
    try:
        delta_subscribed_future, _ = shadow_client.subscribe_to_shadow_delta_updated_events(
            request=iotshadow.ShadowDeltaUpdatedSubscriptionRequest(thing_name=thing_config.thing_name),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_shadow_delta_updated)
    except Exception as e:
        log.error(f"Error:{e} trying to set up shadow_delta update")

    received_all_event.wait()

    # Disconnect
    log.info("Disconnecting...")
    disconnect_future = mqtt_connect.disconnect()
    disconnect_future.result()


if __name__ == '__main__':
    shadow()