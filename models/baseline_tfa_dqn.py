import tensorflow as tf
import streamlit as st
import pandas as pd
from models.monte_carlo import dqn_sim

from tf_agents.environments import  gym_wrapper           # wrap OpenAI gym
from tf_agents.environments import tf_py_environment      # gym to tf gym
from tf_agents.networks import q_network                  # Q net
from tf_agents.agents.dqn import dqn_agent                # DQN Agent
from tf_agents.replay_buffers import tf_uniform_replay_buffer      # replay buffer
from tf_agents.trajectories import trajectory              # s->s' trajectory
from tf_agents.utils import common                       # loss function

from models.abstract import Model


class TFAModel(Model):
    def __init__(self, 
                 environment,
                 params,
                 iterations: int = 20,
                 steps_per_iter: int = 10,
                 repbuffer_len: int = 100000,
                 batch_size: int = 256,
                 learning_r: int = 1e-3,
                 n_eps: int = 10,
                 eval_interval: int = 5,
                 log_interval: int = 1,
                 debugging = False,
                 n_sims: int = 10
                 ): # hyperparameters
        
        self._debugging = debugging

        self._num_iterations = iterations
        self._collect_steps_per_iteration = steps_per_iter
        self._replay_buffer_max_length = repbuffer_len
        self._batch_size = batch_size

        self._learning_rate = learning_r
        self._num_eval_episodes = n_eps 

        self._eval_interval = eval_interval 
        self._log_interval = log_interval

        self._setup_envs(environment, params)
        self._agent, self._repl_buffer = None, None
        self._log, self._returns = None, None
        self._npv = None
        self._n_sims = n_sims
        self._priced = False
        
    def _setup_envs(self, env, params):
        train_gym, eval_gym = env(params), env(params)
        train_gym_wrapper = gym_wrapper.GymWrapper(train_gym)
        eval_gym_wrapper = gym_wrapper.GymWrapper(eval_gym)

        self._train_env = tf_py_environment.TFPyEnvironment(train_gym_wrapper)
        self._eval_env = tf_py_environment.TFPyEnvironment(eval_gym_wrapper)

    def init_agent(self):
        q_net = q_network.QNetwork(
            self._train_env.observation_spec(),
            self._train_env.action_spec(),
            fc_layer_params=(100,)
        )

        opt = tf.keras.optimizers.Adam(learning_rate=self._learning_rate)
        train_step_counter = tf.Variable(0)

        self._agent = dqn_agent.DqnAgent(
            self._train_env.time_step_spec(),
            self._train_env.action_spec(),
            q_network=q_net,
            optimizer=opt,
            td_errors_loss_fn=common.element_wise_squared_loss,
            train_step_counter=train_step_counter
        )
        
        self._agent.initialize()
    
    def _collect_step(self, env, policy, buffer):
        time_step = env.current_time_step()
        action_step = policy.action(time_step)
        next_time_step = env.step(action_step.action)
        trj = trajectory.from_transition(time_step, action_step, next_time_step)

        buffer.add_batch(trj)
    
    def _collect_data(self, env, policy, buffer, steps):
        (self._collect_step(env, policy, buffer) for _ in range(steps))
    
    def build_replay_buffer(self):
        if self._agent is None:
            raise Exception("Agent has not been initialized")

        self._repl_buffer = tf_uniform_replay_buffer.TFUniformReplayBuffer(
            data_spec=self._agent.collect_data_spec,
            batch_size=self._train_env.batch_size,
            max_length=self._replay_buffer_max_length
        )

        dataset = self._repl_buffer.as_dataset(
            num_parallel_calls=3,
            sample_batch_size=self._batch_size,
            num_steps=2).prefetch(3)
        
        self._iterator = iter(dataset)
    
    def _train_iteration(self):
        for n in range(self._collect_steps_per_iteration):
            if self._debugging:
                with open("data/dqn_log.txt", "a") as f:
                    f.write(f"collecting [step = {n}] ...\n")
            self._collect_step(self._train_env, self._agent.collect_policy, self._repl_buffer)
        
        exp, _ = next(self._iterator)
        train_loss = self._agent.train(exp).loss

        step = self._agent.train_step_counter.numpy()
        # with open("data/dqn_log.txt", "a") as f:
        #         f.write(f"step : {step}\n")

        if step % self._log_interval == 0:
            if self._debugging:
                with open("data/dqn_log.txt", "a") as f:
                    f.write(f"step = {step}: loss = {train_loss}\n")
            self._log.append((f"step = {step}", f"loss = {train_loss}"))
        
        if step % self._eval_interval == 0:
            avg_return = dqn_sim(self._agent.policy, self._eval_env, eps=self._num_eval_episodes)
            self._log.append((f"step = {step}", f"Average Return = {avg_return}"))
            self._returns.append(avg_return)

    def train(self):
        if self._repl_buffer is None:
            raise Exception("Unbuilt replay buffer")
        
        self._agent.train = common.function(self._agent.train)

        self._agent.train_step_counter.assign(0)

        avg_return = dqn_sim(self._agent.policy, self._eval_env, eps=self._num_eval_episodes)

        self._log, self._returns = [("Step = 0", f"Average Return = {avg_return}")], [avg_return]

        if not self._debugging:
            bar = st.progress(0.0, text=f"Training Model... (0/{self._num_iterations} Iterations Complete)")
        for i in range(self._num_iterations):
            if self._debugging:
                with open("data/dqn_log.txt", "a") as f:
                    f.write(f"iteration = [{i}]\n")
            else:
                if (i + 1) % self._eval_interval == 0:
                    bar.progress(float((i + 1) / self._num_iterations), text=f"Evaluating Return... ({i + 1}/{self._num_iterations} Iterations Complete)")
                else:
                    bar.progress(float((i + 1) / self._num_iterations), text=f"Training Model... ({i + 1}/{self._num_iterations} Iterations Complete)")
            self._train_iteration()
        if not self._debugging:
            bar.progress(1.0, text="Model Trained")
    
    @property
    def train_iteration_dict(self):
        iterations = [str(x) for x in range(0, self._num_iterations + 1, self._eval_interval)]
        return {
            "Iterations": iterations,
            "Average Return": self._returns
        }
    
    def _highlight_avg_return(self, ser):
        highlight = 'background-color: ccefff'
        default = ''
        return [highlight if 'Average Return' in str(e) else default for e in ser] 
    
    @property
    def train_log(self):
        cols = ["Step", "Metric"]
        log = pd.DataFrame(self._log, columns=cols)
        log.style.apply(self._highlight_avg_return, axis=0, subset=cols)
        return log

    @property
    def train_returns(self):
        return self._returns

    def calculate_npv(self):
        self._npv = dqn_sim(self._agent.policy, self._eval_env, eps=self._n_sims, st_display=True)
        self._priced = True
    
    @property 
    def npv(self):
        return self._npv

    def __str__(self):
        return f"Option Price (Deep Q-Network): ${self.npv}"
    
    def st_visualize(self):
        if not self._priced:
            st.error("Option Not Yet Priced")
            return
        st.success(str(self))
        st.divider()
        st.subheader("Train Iteration Log")
        st.dataframe(self.train_log, use_container_width=True)
        st.divider()
        st.subheader("Graphed Average Returns")
        st.line_chart(self.train_iteration_dict, x="Iterations", y="Average Return" )
        st.divider()
