import sys
import json
import uuid
import threading

from awscrt     import mqtt
from awsiot     import mqtt_connection_builder

# Local

from log        import log
from configs    import thing_config


input_topic = f'$aws/things/{thing_config.thing_name}/#'
received_all_event = threading.Event()


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


def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    """
    Callback when the subscribed topic receives a message
    :param topic:
    :param payload:
    :param dup:
    :param qos:
    :param retain:
    :param kwargs:
    :return:
    """
    log.info(f"Received message from topic '{topic}': {payload}")
    message = json.loads(payload.decode('utf-8'))

def on_connection_success(connection, callback_data):
    """
    Callback when the connection successfully connects
    :param connection:
    :param callback_data:
    :return:
    """
    assert isinstance(callback_data, mqtt.OnConnectionSuccessData)
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


if __name__ == '__main__':

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

    # Subscribe
    subscribe_future, packet_id = mqtt_connect.subscribe(
        topic=input_topic,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_message_received)

    subscribe_result = subscribe_future.result()
    log.info("Subscribed with {} topic:{}".format(str(subscribe_result['qos']),input_topic))
    received_all_event.wait()

    # Disconnect
    print("Disconnecting...")
    disconnect_future = mqtt_connect.disconnect()
    disconnect_future.result()
    print("Disconnected!")
