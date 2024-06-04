import cv2
import matplotlib.pyplot as plt
import numpy as np
import asyncio
from bleak import BleakClient, BleakScanner


IMG_SIZE = 640
DEVICE_UUID = "C908703E-4430-520B-99A2-A5C5598BED8E"
SERVICE_UUID = "2f5772da-18e3-4f2e-82ab-910e81b9f232"
ENGINE_CHAR_UUID = "165aecf8-ed44-45e7-aae4-63789234a30f"

LOW_B = np.uint8([0, 0, 0])
HIGH_B = np.uint8([5, 5, 5])


class Controller:
    def __init__(self, duration=32, post_function=None):
        self.post_function = post_function

    def move_forward(self):
        byte_array = self.values_to_bytearray([1, 255, 32], [0, 255, 32], [0, 0, 0])
        self.post_function(byte_array)

    def turn_left(self):
        byte_array = self.values_to_bytearray([1, 255, 32], [1, 150, 32], [0, 0, 0])
        self.post_function(byte_array)

    def turn_right(self):
        byte_array = self.values_to_bytearray([1, 150, 32], [0, 255, 32], [0, 0, 0])
        self.post_function(byte_array)


def values_to_bytearray(m1, m2, m3):
    arr = np.array([m1, m2, m3]).flatten().tolist()

    return bytearray(arr)


def preprocess_frame(frame):
    frame = cv2.GaussianBlur(frame, (5, 5), 0)
    frame = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
    return frame


def filter_red(image):
    # Convert the image to HSV color space
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Define range for red color
    lower_red = np.array([0, 120, 70])
    upper_red = np.array([10, 255, 255])

    # Create a mask for red color
    mask1 = cv2.inRange(hsv, lower_red, upper_red)

    lower_red = np.array([170, 120, 70])
    upper_red = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red, upper_red)

    # Combine the masks
    mask = mask1 + mask2
    return mask


def compute_direction(frame, low_b, high_b):
    # mask = cv2.inRange(frame, low_b, high_b)
    mask = filter_red(frame)
    contours, hierarchy = cv2.findContours(mask, 1, cv2.CHAIN_APPROX_NONE)
    direction = None
    if len(contours) > 0:
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            print(f"cX: {cX}, cY: {cY}")
            if cX > IMG_SIZE / 3 * 2:
                print("right")
                direction = "right"

            if cX < IMG_SIZE / 3:
                print("left")
                direction = "left"

            if cX > IMG_SIZE / 3 and cX < IMG_SIZE / 3 * 2:
                print("forward")
                direction = "forward"
            cv2.circle(frame, (cX, cY), 5, (0, 0, 255), -1)
    else:
        print("no contours")

    cv2.drawContours(frame, contours, -1, (0, 255, 0), 5)
    cv2.imshow("frame", frame)
    cv2.imshow("mask", mask)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        return

    return direction


async def run():
    cap = cv2.VideoCapture(0)  # iphone continuity camera
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    async with BleakClient(DEVICE_UUID) as client:
        if await client.is_connected():
            print(f"Connected to {DEVICE_UUID}")

            try:
                while True:
                    # get image
                    ret, frame = cap.read()
                    if not ret:
                        print("Error: Could not read frame.")
                        break
                    frame = preprocess_frame(frame)
                    direction = compute_direction(frame, LOW_B, HIGH_B)
                    # turn off the steering part
                    # direction = None
                    if direction == "left":
                        byte_array = values_to_bytearray(
                            [1, 255, 32], [1, 255, 32], [0, 0, 0]
                        )
                        await client.write_gatt_char(ENGINE_CHAR_UUID, byte_array)

                    if direction == "right":
                        byte_array = values_to_bytearray(
                            [0, 255, 32], [0, 255, 32], [0, 0, 0]
                        )
                        await client.write_gatt_char(ENGINE_CHAR_UUID, byte_array)

                    if direction == "forward":
                        byte_array = values_to_bytearray(
                            [1, 255, 32], [0, 255, 32], [0, 0, 0]
                        )
                        await client.write_gatt_char(ENGINE_CHAR_UUID, byte_array)

                    if direction is None:
                        byte_array = values_to_bytearray(
                            [1, 0, 0], [0, 0, 0], [0, 0, 0]
                        )
                        print(f"No direction found, stopping engine: {byte_array}")
                        await client.write_gatt_char(ENGINE_CHAR_UUID, byte_array)

                    await asyncio.sleep(0.1)

            except Exception as e:
                print(f"    Failed to write characteristic {ENGINE_CHAR_UUID}: {e}")

        else:
            print(f"Failed to connect to {DEVICE_UUID}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(run())
