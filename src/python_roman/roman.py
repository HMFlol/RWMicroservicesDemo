import os
import json
import psycopg2
from confluent_kafka import Consumer, Producer

class RomanMicroservice:
    def __init__(self):

        # Check if required environment variables are set
        required_env_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
        if missing_vars:
            print(f"Missing required environment variables: {', '.join(missing_vars)}")
            exit(1)
        self.bootstrap_servers = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:9092')
        self.input_topic = os.environ.get('INPUT_TOPIC', 'stage4')
        self.output_topic = os.environ.get('OUTPUT_TOPIC', 'stage5')
        self.db_host = os.environ.get('DB_HOST', 'localhost')
        self.db_port = os.environ.get('DB_PORT', '5432')
        self.db_name = os.environ.get('DB_NAME')
        self.db_user = os.environ.get('DB_USER')
        self.db_password = os.environ.get('DB_PASSWORD')
        self.consumer = None
        self.producer = None


    def start(self):
        # Create a Kafka consumer
        self.consumer = Consumer({
            'bootstrap.servers': self.bootstrap_servers,
            'group.id': 'roman_microservice'
        })
        self.consumer.subscribe([self.input_topic])

        # Create a Kafka producer
        self.producer = Producer({'bootstrap.servers': self.bootstrap_servers})

        # Start consuming messages
        while True:
            message = self.consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                print(f"Consumer error: {message.error()}")
                continue

            # Process the received message
            data = self.deserialize_message(message.value())

            roman = {}
            # Add the result to the input JSON object with a dynamic key name
            for t in ['sum', 'product', 'lcm']:
                roman[t] = self.convert_to_roman(data[t])

            # Save the result to the Postgres table
            self.insert_into_postgres(data['numbers'], roman)

            # Publish the updated JSON object to the output topic
            self.publish_result(data)

    def deserialize_message(self, message):
        # Deserialize JSON message
        return json.loads(message)

    def insert_into_postgres(self, numbers, data):
        # Connect to the Postgres database
        conn = psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password
        )
        cursor = conn.cursor()
        create_table_query = """
            CREATE TABLE IF NOT EXISTS results (

                numbers TEXT,
                stage TEXT,
                result TEXT
            )
        """
        cursor.execute(create_table_query)

        # Insert the result into the table
        cursor.execute(f"INSERT INTO results (numbers, stage, result) VALUES (%s, %s, %s)", (json.dumps(numbers), 'stage4', json.dumps(data)))

        # Commit the transaction and close the connection
        conn.commit()
        cursor.close()
        conn.close()

    def publish_result(self, data):
        # Serialize JSON object
        payload = json.dumps(data)

        # Publish the result to the output topic
        self.producer.produce(self.output_topic, value=payload.encode('utf-8'))

        # Flush the producer tomake sure the message is sent
        self.producer.flush()

    def convert_to_roman(number):
        roman_numerals = {
            1000: 'M',
            900: 'CM',
            500: 'D',
            400: 'CD',
            100: 'C',
            90: 'XC',
            50: 'L',
            40: 'XL',
            10: 'X',
            9: 'IX',
            5: 'V',
            4: 'IV',
            1: 'I'
        }

        result = ''
        for value, symbol in roman_numerals.items():
            while number >= value:
                result += symbol
                number -= value
        return result


if __name__ == '__main__':
    microservice = RomanMicroservice()

    microservice.start()
