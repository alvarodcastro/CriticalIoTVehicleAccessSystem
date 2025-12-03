## Sensor and actuators
For each sensor measurement data sent over the CAN. We should construct a specification for its corresponding translation. For example, for temperature data:
- Temperature sensor IDs will be in the range 0x400-0x500
- 2 Bytes used
- Ranges from 0ºC to 99.99ºC
- Only 2 decimals for ºC
- Conversion factor will be as follows: (TEMP x 100)
- Then converted into hex to send over CAN using 2 bytes
- So, 85.31ºC -> 8531 -> 0x2152 -> MSB=21, LSB=52
- CAN message will be: 423#022152 for sensor with ID 423
### Air quality 
Needs no ACK, just send measures
### Gas 
Needs no ACK, just send measures
### Ultrasound
Sensor for detecting presence in the parking spot. Will have a led attached to indicate locally whether the spot is busy or not. Independently the data will be sent over CAN, Needs no ACK, just send measures.
### Servo
Simulating barrier. Barrier will constantly send their state, which along with the identifier will provide a complete understanding of barrier(s) state.
