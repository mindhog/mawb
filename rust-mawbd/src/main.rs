#![allow(unused_imports)]

use jack::{AsyncClient, AudioIn, AudioOut, Client, ClientStatus, Control,
    ClientOptions, Error, Frames, Port, PortId,
    ProcessHandler, ProcessScope, NotificationHandler};
use std::mem;
use std::time::Duration;

struct DefaultNotificationHandler {}

impl NotificationHandler for DefaultNotificationHandler {
    fn thread_init(&self, _: &Client) {
        println!("Thread initialized");
    }
    fn shutdown(&mut self, _status: ClientStatus, _reason: &str) {
        println!("Shutting down");
    }
    fn freewheel(&mut self, _: &Client, _is_freewheel_enabled: bool) {
        println!("Freewheel");
    }
    fn sample_rate(&mut self, _: &Client, _srate: Frames) -> Control {
        println!("sample_rate");
        return Control::Continue;
    }
    fn client_registration(
        &mut self,
        _: &Client,
        _name: &str,
        _is_registered: bool
    ) {
        println!("client registered");
    }
    fn port_registration(
        &mut self,
        _: &Client,
        _port_id: PortId,
        _is_registered: bool
    ) {
        println!("port registered");
    }
    fn port_rename(
        &mut self,
        _: &Client,
        _port_id: PortId,
        _old_name: &str,
        _new_name: &str
    ) -> Control {
        println!("port renamed");
        return Control::Continue;
    }
    fn ports_connected(
        &mut self,
        _: &Client,
        _port_id_a: PortId,
        _port_id_b: PortId,
        _are_connected: bool
    ) {
        println!("port connected");
    }
    fn graph_reorder(&mut self, _: &Client) -> Control {
        println!("Graph rendered");
        return Control::Continue;
    }
    fn xrun(&mut self, _: &Client) -> Control {
        println!("xrun");
        return Control::Continue;
    }
}

struct MyProcessHandler {}
impl ProcessHandler for MyProcessHandler {
    fn process(&mut self, _: &Client, _process_scope: &ProcessScope) ->
            Control {
        return Control::Continue;
    }
}

trait Processor {
    fn process(&mut self, client: &Client);
}

type MyAsyncClient = AsyncClient<DefaultNotificationHandler, MyProcessHandler>;

enum ClientState {
    Active(MyAsyncClient),
    Inactive(Client),
    Undefined,
}

use crate::ClientState::{Active, Inactive, Undefined};

/// The jack processing engine.
struct AudioEngine {
    client: ClientState,
    looping : bool,
}

impl AudioEngine {
    /// Create a new AudioEngine, `name` is the name of the jack client.
    fn new(name: &str) -> Result<AudioEngine, Error> {
        let (client, _status) = Client::new(name, ClientOptions::empty())?;
        // let active_client =
        //    client.activate_async(DefaultNotificationHandler {}, handler)?;
        // let borrowed_client = active_client.as_client();
        Ok(AudioEngine {client: Inactive(client), looping: false})
    }

    fn activate(&mut self) {
        let client_state = mem::replace(&mut self.client, Undefined);
        if let Inactive(c) = client_state {
            self.client =
                Active(
                    c.activate_async(DefaultNotificationHandler{},
                                     MyProcessHandler {}
                                     ).unwrap()
                );
        } else {
            self.client = client_state;
        }
    }

    fn deactivate(&mut self) {
        let client_state = mem::replace(&mut self.client, Undefined);
        if let Active(c) = client_state {
            self.client = Inactive(c.deactivate().unwrap().0)
        } else {
            self.client = client_state;
        }
    }

    /// Register a new input port with the spsecified name.
    fn register_input_port(&mut self, name: &str) -> Result<Port<AudioIn>, Error> {
        return match &self.client {
            Active(_) => {
                self.deactivate();
                let result;
                match &self.client {
                    Inactive(c) => {
                        result = c.register_port(name, AudioIn::default());
                        self.activate();
                        result
                    },
                    Active(_) => return Err(Error::ClientDeactivationError),
                    Undefined => return Err(Error::ClientDeactivationError),
                }
            },
            Inactive(c) => c.register_port(name, AudioIn::default()),
            Undefined => Err(Error::ClientDeactivationError),
        }
    }

    /// Register a new output port with the spsecified name.
    fn register_output_port(&mut self, name: &str) ->
            Result<Port<AudioOut>, Error> {
        return match &self.client {
            Active(_) => {
                self.deactivate();
                self.activate();
                let result;
                match &self.client {
                    Inactive(c) => {
                        result = c.register_port(name, AudioOut::default());
                        self.activate();
                        result
                    },
                    Active(_) => return Err(Error::ClientDeactivationError),
                    Undefined => return Err(Error::ClientDeactivationError),
                }
            },
            Inactive(c) => c.register_port(name, AudioOut::default()),
            Undefined => return Err(Error::ClientDeactivationError),
        }
    }
}

fn run_process() -> Result<(), Error> {
    let mut jack_engine = AudioEngine::new("mawbd")?;
    jack_engine.register_input_port("in_1")?;
    jack_engine.register_input_port("in_2")?;
    jack_engine.register_output_port("out_1")?;
    jack_engine.register_output_port("out_2")?;

    loop {
        std::thread::sleep(Duration::from_millis(1000));
    }
    // return 0;
}

fn main() {
    std::process::exit(
        match run_process() {
            Ok(()) => 0,
            Err(message) => {
                println!("Error creating jack client: {}", message);
                1
            }
        }
    );
}
