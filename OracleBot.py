import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Computer, Bot, BotAI
from sc2.constants import UnitTypeId, UpgradeId, AbilityId, BuffId
import random
from sc2.position import Point2, Point3
from typing import Union
from math import sqrt
from sc2.units import Units, Unit


def get_pylon_pos_in_bitownhall(map_center, townhall_location, interval):
    dirt = (
        map_center.x - townhall_location.x,
        map_center.y - townhall_location.y
    )
    length = sqrt(dirt[0]**2 +dirt[1]**2)
    pos1 = Point2((
        int((dirt[0] / length)*interval + townhall_location.x),
        int((dirt[1] / length)*interval + townhall_location.y)
    ))
    pos2 = Point2((
        int(townhall_location.x),
        pos1.y
    ))
    pos3 = Point2((
        pos1.x,
        int(townhall_location.y)
    ))
    return [pos1, pos2, pos3]

def get_pylon_pos_by_initial(p: tuple):
    pos_list = []
    pos_list.append(p)
    pos_list.append((0, p[1]))
    pos_list.append((p[0], 0))
    pos_list.append((-p[0], -p[1]))
    pos_list.append((-p[0], p[1]))
    pos_list.append((p[0], -p[1]))

    pos_list.append((2 * p[0], 2 * p[1]))
    pos_list.append((0, 2 * p[1]))
    pos_list.append((2 * p[0], 0))
    pos_list.append((-2 * p[0], 2 * p[1]))
    pos_list.append((2 * p[0], -2 * p[1]))
    return pos_list

# def get_direction(tail: Point2, head: Point2):


class OracleBot(BotAI):

    def __init__(self):
        super().__init__()

        self.pylon_pos : list
        # self.oracle_allow_sneakattack = True
        self.enemy_townhall_locations = []
        self.scout_oracle = None

        self.pylon_control = 0
        self.pylon_interval = 6
        self.is_building = False
        self.can_attack_oracle_units = {UnitTypeId.HYDRALISK, UnitTypeId.QUEEN, UnitTypeId.MUTALISK, UnitTypeId.CORRUPTOR, UnitTypeId.RAVAGER}

        self.oracle_next_loction = None
        self.target_of_oracle = None
        self.gather_point = None

        self.gather_in_home = True
        self.defend_home = False
        self.all_force_attack = False
        self.have_resource_exhausted = False

        self.attack_leader = None # Unit

        self.gather_range = 5


    async def on_step(self, iteration: int):
        self.iteration = iteration
        # self.pylon_interval = 12

        self.max_gateway = 10
        await self.distribute_workers()
        await self.train_workers()
        await self.build_pylon()
        await self.build_stargate()
        await self.train_oracle()

        await self.upgrade_charge()
        await self.upgrade_blink()
        await self.upgrade_resonating_glaives()
        await self.upgrade_forge()

        await self.build_assimilators()
        await self.build_gateway_warpgate()
        await self.upgrade_warpgate()
        await self.train_force_in_gate()

        await self.expand()
        await self.build_roboticsfacility()
        await self.sneak_attack_oracle()
        await self.attack_oracle()

        await self.distribute_chronoboost()
        await self.gather_froces()
        await self.build_forge()

        await self.build_twilightcouncil()

        await self.all_attack()
        await self.defensive()


        await self.train_force()

        # self.get_scout()
        self.deal_with_information()

        await self.output_information_async()
        self.output_information_normal()

    def get_scout(self):
        if self.scout_oracle is None and self.units(UnitTypeId.ORACLE).ready.exists:
            for oracle in self.units(UnitTypeId.ORACLE).ready:
                if oracle.health >= 20 and oracle.health >= 20:
                    self.scout_oracle = oracle
                    break
        if self.scout_oracle.health <= 1 and self.scout_oracle.shield <= 1: self.scout_oracle = None

    def deal_with_information(self):
        if len(self.enemy_townhall_locations) == 0: self.enemy_townhall_locations.append(self.enemy_start_locations[0])

        if self.target_of_oracle is not None:
            if self.target_of_oracle.tag not in [u.tag for u in self.known_enemy_units]:
                self.target_of_oracle = None

        # about gather point
        if self.units(UnitTypeId.PYLON).exists:
            self.gather_point = self.units(UnitTypeId.PYLON).closest_to(self.enemy_start_locations[0]).position.to2
            map_center = self.game_info.map_center
            direction = self.gather_point.direction_vector(map_center) * 3
            self.gather_point = self.gather_point + direction

        # about attack
        if self.units.of_type({UnitTypeId.STALKER, UnitTypeId.ZEALOT, UnitTypeId.ADEPT}).ready.exists:
            if self.units(UnitTypeId.IMMORTAL).ready.exists and \
                self.units.of_type({UnitTypeId.STALKER, UnitTypeId.ZEALOT, UnitTypeId.ADEPT}).ready.closer_than(10, self.gather_point).amount > 10:
                self.gather_in_home = False
                self.all_force_attack = True

        # about attack leader
        if self.all_force_attack == True:
            if self.units(UnitTypeId.IMMORTAL).ready.exists:
                self.attack_leader = self.units(UnitTypeId.IMMORTAL).ready.closest_to(self.enemy_start_locations[0])

            # if self.attack_leader is None or self.attack_leader not in self.units:
            #     self.attack_leader = self.units(UnitTypeId.IMMORTAL).ready.first
            # elif self.attack_leader is not None and self.attack_leader not in self.units and self.units(UnitTypeId.IMMORTAL).ready.amount == 0:
            #     if self.units.filter(lambda u:u.is_attacking).exists:
            #         self.attack_leader = self.units.filter(lambda u:u.is_attacking).random
            #     else:
            #         self.all_force_attack = False
            #         self.gather_in_home = True

        # about defensive
        self.defend_home = not self.enemy_appeared_near_townhall()

        # about exhausted resource
        if not self.have_resource_exhausted:
            for townhall in self.townhalls.ready:
                if townhall.ideal_harvesters <= 12:
                    self.have_resource_exhausted = True

    def enemy_appeared_near_townhall(self) -> bool:
        for townhall in self.townhalls:
            if self.known_enemy_units.closer_than(16, townhall).exists:
                return True
        return False

    def investigate(self):
        pass

    async def output_information_async(self):
        pass

    def output_information_normal(self):
        if self.attack_leader is not None:
            print("leader = ", self.attack_leader, "position=", self.attack_leader.position)

    async def chronoboost(self, target):
        for townhall in self.townhalls:
            if townhall.energy > 50:
                await self.do(townhall(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, target = target))
                break


    async def distribute_chronoboost(self):
        for townhall in self.townhalls.ready:
            needworkers = townhall.ideal_harvesters
            for geyser in self.units(UnitTypeId.ASSIMILATOR).ready.closer_than(8, townhall):
                needworkers += geyser.ideal_harvesters

            if self.units(UnitTypeId.PROBE).closer_than(16, townhall).amount < needworkers - 3 \
                    and not townhall.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                await self.chronoboost(townhall)

        for stargate in self.units(UnitTypeId.STARGATE).ready:
            if not stargate.is_idle and not stargate.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                await self.chronoboost(stargate)

        if 0 < self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) < 1 \
                and not self.units(UnitTypeId.CYBERNETICSCORE).ready.first.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
            await self.chronoboost(self.units(UnitTypeId.CYBERNETICSCORE).ready.first)

    async def train_workers(self):
        for townhall in self.townhalls.ready:
            needworkers = townhall.ideal_harvesters
            for geyser in self.geysers.closer_than(8, townhall).ready:
                needworkers += geyser.ideal_harvesters
            workers_nearby = self.workers.closer_than(20, townhall).amount
            if workers_nearby < needworkers and self.can_afford(UnitTypeId.PROBE) and townhall.is_idle:
                await self.do(townhall.train(UnitTypeId.PROBE))


    async def build_pylon(self):
        if self.townhalls.not_ready.exists:
            for townhall in self.townhalls.not_ready:
                if not self.units(UnitTypeId.PYLON).closer_than(self.pylon_interval+1, townhall).exists:
                    pylon_pos = get_pylon_pos_in_bitownhall(self.game_info.map_center, townhall.position, self.pylon_interval)
                    if self.can_afford(UnitTypeId.PYLON):
                        await self.build(UnitTypeId.PYLON, near = pylon_pos[0])

        if self.supply_left < 5 and self.supply_cap < 200 and self.can_afford(UnitTypeId.PYLON) and self.already_pending(UnitTypeId.PYLON) < self.townhalls.amount:
            map_center = self.game_info.map_center
            dir = (int( (map_center.x - self.start_location.x) / abs(map_center.x - self.start_location.x)),
                    int( (map_center.y - self.start_location.y) / abs(map_center.y - self.start_location.y)))
            pylon_pos = get_pylon_pos_by_initial(dir)

            rand_control = True

            if self.units(UnitTypeId.PYLON).closer_than(2*self.pylon_interval+1, self.start_location).amount < len(pylon_pos):
                rand_control = False
                index = self.units(UnitTypeId.PYLON).closer_than(2*self.pylon_interval+1, self.start_location).amount
                this_pylon_pos = Point2(
                    (pylon_pos[index][0]*self.pylon_interval + self.start_location.x,
                     pylon_pos[index][1]*self.pylon_interval + self.start_location.y)
                )
                await self.build(UnitTypeId.PYLON, near = this_pylon_pos)
            else:
                for townhall in self.townhalls:
                    amount = self.units(UnitTypeId.PYLON).closer_than(9, townhall).amount
                    if amount < 3:
                        rand_control = False
                        pylon_pos = get_pylon_pos_in_bitownhall(self.game_info.map_center, townhall.position,
                                                                self.pylon_interval)
                        if self.can_afford(UnitTypeId.PYLON): await self.build(UnitTypeId.PYLON, near=pylon_pos[amount])

            if rand_control and self.can_afford(UnitTypeId.PYLON):
                await self.build(UnitTypeId.PYLON, near=self.units(UnitTypeId.PYLON).ready.random)

    async def build_assimilators(self):
        for nexus in self.townhalls.ready:
            if self.units(UnitTypeId.PYLON).closer_than(25, nexus).exists:
                vespenes = self.state.vespene_geyser.closer_than(10, nexus)
                for vespene in vespenes:
                    if self.can_afford(UnitTypeId.ASSIMILATOR):
                        worker = self.select_build_worker(vespene.position)
                        if worker is not None and not self.units(UnitTypeId.ASSIMILATOR).closer_than(1.0, vespene).exists:
                            await self.do(worker.build((UnitTypeId.ASSIMILATOR), vespene))

    async def build_gateway_warpgate(self):
        if not self.units(UnitTypeId.CYBERNETICSCORE).ready.exists and not self.already_pending(UnitTypeId.CYBERNETICSCORE):
            if not self.units(UnitTypeId.GATEWAY).ready.exists and not self.already_pending(UnitTypeId.GATEWAY):
                if self.can_afford(UnitTypeId.GATEWAY):
                    if self.units(UnitTypeId.PYLON).ready.exists:
                        pylon = self.units(UnitTypeId.PYLON).ready.random
                        await self.build(UnitTypeId.GATEWAY, near = pylon)
            elif self.units(UnitTypeId.GATEWAY).ready.exists and not self.already_pending(UnitTypeId.CYBERNETICSCORE):
                await self.build(UnitTypeId.CYBERNETICSCORE, near = self.units(UnitTypeId.GATEWAY).ready.random)
        elif self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            if self.units(UnitTypeId.GATEWAY).amount + self.units(UnitTypeId.WARPGATE).amount < self.townhalls.ready.amount*3 and \
                    self.already_pending(UnitTypeId.GATEWAY) < 2 and\
                    self.units(UnitTypeId.GATEWAY).amount + self.units(UnitTypeId.WARPGATE).amount < self.max_gateway:
                townhall_no_gateway = None
                for townhall in self.townhalls.ready:
                    if self.units(UnitTypeId.WARPGATE).closer_than(10, townhall).amount == 0 and\
                            not self.units(UnitTypeId.WARPGATE).not_ready.closer_than(10, townhall).exists and\
                            self.units(UnitTypeId.PYLON).closer_than(10, townhall).ready.amount > 0:
                        townhall_no_gateway = townhall
                        break
                if townhall_no_gateway is None:
                    await self.build(UnitTypeId.GATEWAY, near = self.units(UnitTypeId.PYLON).ready.random)
                else:
                    pylon = self.units(UnitTypeId.PYLON).closer_than(10, townhall_no_gateway).ready.random
                    await self.build(UnitTypeId.GATEWAY, near = pylon)



    async def upgrade_warpgate(self):
        if self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            BY = self.units(UnitTypeId.CYBERNETICSCORE).ready.first
            if self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 0:
                abilities = await self.get_available_abilities(BY)
                if AbilityId.RESEARCH_WARPGATE in abilities:
                    await self.do(BY.research(UpgradeId.WARPGATERESEARCH))

    async def train_force_in_gate(self):
        if self.townhalls.ready.amount == 1:
            if self.units(UnitTypeId.GATEWAY).ready.exists and not self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
                if self.units(UnitTypeId.ZEALOT).ready.amount < 1:
                    await self.train_zealot()
            elif self.units(UnitTypeId.GATEWAY).ready.exists and self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
                if self.units(UnitTypeId.ADEPT).ready.amount < 2:
                    await self.train_adept()
                if self.units(UnitTypeId.STALKER).ready.amount < 1:
                    await self.train_stalker()
            elif self.units(UnitTypeId.WARPGATE).ready.exists and \
                    self.units.of_type({UnitTypeId.ZEALOT, UnitTypeId.STALKER, UnitTypeId.ADEPT}).amount < 5:
                if self.units(UnitTypeId.ADEPT).amount < self.units(UnitTypeId.ZEALOT).amount:
                    await self.train_stalker()
                else:
                    await self.train_zealot()
        elif self.townhalls.ready.amount >= 2:
            if self.units(UnitTypeId.STALKER).amount < self.known_enemy_units.of_type({UnitTypeId.ZERGLING}).amount / 3:
                await self.train_adept()
            if self.units(UnitTypeId.ZEALOT).amount < self.known_enemy_units.of_type({UnitTypeId.ROACH, UnitTypeId.RAVAGER}).amount:
                await self.train_zealot()
            if self.units(UnitTypeId.STALKER).amount < self.known_enemy_units.filter(lambda u:u.is_flying).amount:
                await self.train_stalker()
            if self.units(UnitTypeId.STALKER).amount >= self.known_enemy_units.of_type({UnitTypeId.ZERGLING}).amount / 3 and \
                self.units(UnitTypeId.ZEALOT).amount >= self.known_enemy_units.of_type({UnitTypeId.ROACH, UnitTypeId.RAVAGER}).amount and \
                self.units(UnitTypeId.STALKER).amount >= self.known_enemy_units.filter(lambda u:u.is_flying).amount and \
                self.units(UnitTypeId.IMMORTAL).amount >= 3:

                if self.units(UnitTypeId.ZEALOT).amount <= self.units(UnitTypeId.STALKER).amount*2:
                    await self.train_zealot()
                elif self.units(UnitTypeId.ADEPT).amount <= self.units(UnitTypeId.ZEALOT).amount:
                    await self.train_adept()
                else:
                    await self.train_stalker()

    async def train_adept(self):
        if not self.units(UnitTypeId.WARPGATE).ready.exists and \
                self.units(UnitTypeId.GATEWAY).ready.exists and \
                self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            for gateway in self.units(UnitTypeId.GATEWAY).ready:
                if self.can_afford(UnitTypeId.ADEPT) and gateway.is_idle:
                    await self.do(gateway.train(UnitTypeId.ADEPT))
        elif self.units(UnitTypeId.WARPGATE).ready.exists and self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            # proxy = self.units(UnitTypeId.PYLON).ready.random.position.to2
            proxy = self.units(UnitTypeId.WARPGATE).ready.furthest_to(self.start_location).position.to2
            if self.can_afford(UnitTypeId.ADEPT):
                for warpgate in self.units(UnitTypeId.WARPGATE).ready:
                    abilities = await self.get_available_abilities(warpgate)
                    if AbilityId.WARPGATETRAIN_ZEALOT in abilities:
                        pos = proxy.random_on_distance(4)
                        placement = await self.find_placement(UnitTypeId.PYLON, pos)
                        if placement is not None: await self.do(warpgate.warp_in(UnitTypeId.ADEPT, pos))

    async def train_zealot(self):
        if not self.units(UnitTypeId.WARPGATE).ready.exists and \
                self.units(UnitTypeId.GATEWAY).ready.exists:
            for gateway in self.units(UnitTypeId.GATEWAY).ready:
                if self.can_afford(UnitTypeId.ZEALOT) and gateway.is_idle:
                    await self.do(gateway.train(UnitTypeId.ZEALOT))
        elif self.units(UnitTypeId.WARPGATE).ready.exists:
            proxy = self.units(UnitTypeId.WARPGATE).ready.furthest_to(self.start_location).position.to2
            # proxy = self.units(UnitTypeId.PYLON).ready.random.position.to2
            if self.can_afford(UnitTypeId.ZEALOT):
                for warpgate in self.units(UnitTypeId.WARPGATE).ready:
                    abilities = await self.get_available_abilities(warpgate)
                    if AbilityId.WARPGATETRAIN_ZEALOT in abilities:
                        pos = proxy.random_on_distance(4)
                        placement = await self.find_placement(UnitTypeId.PYLON, pos)
                        if placement is not None: await self.do(warpgate.warp_in(UnitTypeId.ZEALOT, pos))

    async def train_stalker(self):
        if not self.units(UnitTypeId.WARPGATE).ready.exists and \
                self.units(UnitTypeId.GATEWAY).ready.exists and \
                self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            for gateway in self.units(UnitTypeId.GATEWAY).ready:
                if self.can_afford(UnitTypeId.STALKER) and gateway.is_idle:
                    await self.do(gateway.train(UnitTypeId.STALKER))
        elif self.units(UnitTypeId.WARPGATE).ready.exists and self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            # proxy = self.units(UnitTypeId.PYLON).ready.random.position.to2
            proxy = self.units(UnitTypeId.WARPGATE).ready.furthest_to(self.start_location).position.to2
            if self.can_afford(UnitTypeId.STALKER):
                for warpgate in self.units(UnitTypeId.WARPGATE).ready:
                    abilities = await self.get_available_abilities(warpgate)
                    if AbilityId.WARPGATETRAIN_ZEALOT in abilities:
                        pos = proxy.random_on_distance(4)
                        placement = await self.find_placement(UnitTypeId.PHOTONCANNON, pos)
                        if placement is not None: await self.do(warpgate.warp_in(UnitTypeId.STALKER, pos))

    async def gather_froces(self):
        if self.gather_in_home or not self.defend_home:
            for unit in self.units.of_type({UnitTypeId.ZEALOT, UnitTypeId.ADEPT, UnitTypeId.STALKER, UnitTypeId.IMMORTAL}).ready.idle:
                if unit.distance_to(self.gather_point) > self.gather_range:
                    await self.do(unit.move(self.gather_point))


    async def build_stargate(self):
        if self.units(UnitTypeId.CYBERNETICSCORE).ready.exists:
            pylon = self.units(UnitTypeId.PYLON).closer_than(25, self.start_location).ready.random
            if self.can_afford(UnitTypeId.STARGATE):
                if self.units(UnitTypeId.STARGATE).amount < self.townhalls.ready.amount and not self.already_pending(UnitTypeId.STARGATE):
                    await self.build(UnitTypeId.STARGATE, near = pylon)

    async def train_oracle(self):
        if self.units(UnitTypeId.STARGATE).ready.exists:
            if self.can_afford(UnitTypeId.ORACLE):
                if self.units(UnitTypeId.ORACLE).amount < 3:
                    for stargate in self.units(UnitTypeId.STARGATE):
                        if stargate.is_idle:
                            await self.do(stargate.train(UnitTypeId.ORACLE))


    def oracle_select_enemy_worker_as_target(self, workers : Units):
        for worker in workers:
            if self.known_enemy_units.of_type(self.can_attack_oracle_units).closer_than(6, worker).amount < 2 and \
                    self.known_enemy_structures({UnitTypeId.SPORECRAWLER}).closer_than(6, worker).amount < 1:
                return worker
        return None


    async def oracle_attck_target(self, oracle:Unit, target: Unit):
        if AbilityId.BEHAVIOR_PULSARBEAMON in await self.get_available_abilities(oracle):
            await self.do(oracle(AbilityId.BEHAVIOR_PULSARBEAMON))
        await self.do(oracle.attack(target))

    def oracle_get_enemy_next_base(self, oracle:Unit):
        for loction in self.enemy_townhall_locations:
            if oracle.distance_to(loction) > 20:
                return loction

    async def oracle_flee(self, oracle:Unit):
        if AbilityId.BEHAVIOR_PULSARBEAMOFF in await self.get_available_abilities(oracle):
            await self.do(oracle(AbilityId.BEHAVIOR_PULSARBEAMOFF))
        await self.oracle_move_with_dodge(oracle, self.start_location)

    async def sneak_attack_oracle(self):
        for oracle in self.units(UnitTypeId.ORACLE).ready.filter(lambda u:u.health >= 15):
            if oracle.health + oracle.shield < 0.4*(oracle.health_max + 60):  # if hp is low
                if self.known_enemy_units.closer_than(15, oracle).exists:                # if enemies nearby
                    if self.known_enemy_units.of_type(self.can_attack_oracle_units).closer_than(12, oracle).exists or \
                            self.known_enemy_structures.of_type({UnitTypeId.SPORECRAWLER}).exists: # if enemies can attack you
                        await self.oracle_flee(oracle)
                    else:
                        await self.do(oracle.hold_position())
                else:
                    await self.do(oracle.hold_position())
            elif oracle.health + oracle.shield > 0.6*(oracle.health_max + 60):  # if hp is high
                if oracle.energy < 5 : # oracle has no enough energy
                    if self.known_enemy_units.of_type(self.can_attack_oracle_units).closer_than(12, oracle).exists or \
                            self.known_enemy_structures.of_type({UnitTypeId.SPORECRAWLER}).exists: # if enemies can attack you
                        await self.oracle_flee(oracle)
                    else:
                        await self.do(oracle.hold_position())
                else:  # oracle has enough energy
                    if oracle.energy > 35:
                        if self.known_enemy_units.closer_than(12, oracle).exists: # if enemies nearby
                            if self.known_enemy_units.closer_than(8, oracle).of_type({UnitTypeId.DRONE}).exists: # enemies have workers
                                if self.target_of_oracle is None:
                                    self.target_of_oracle = self.oracle_select_enemy_worker_as_target(self.known_enemy_units.closer_than(4, oracle).of_type({UnitTypeId.DRONE}))
                                if self.target_of_oracle is None:
                                    if self.oracle_next_loction == None or oracle.distance_to(self.oracle_next_loction) < 5:
                                        self.oracle_next_loction = self.oracle_get_enemy_next_base(oracle)
                                    if self.oracle_next_loction is not None:
                                        # await self.do(oracle.move(self.oracle_next_loction))
                                        await self.oracle_move_with_dodge(oracle, self.oracle_next_loction)
                                else:
                                    await self.oracle_attck_target(oracle, self.target_of_oracle)
                            else:
                                if self.known_enemy_units.closer_than(10, oracle).of_type({UnitTypeId.HYDRALISK, UnitTypeId.MUTALISK, UnitTypeId.QUEEN}).amount > 2: # enemy is strong enough
                                    await self.oracle_flee(oracle)
                                else:
                                    if self.oracle_next_loction == None or oracle.distance_to(self.oracle_next_loction) < 5:
                                        self.oracle_next_loction = self.oracle_get_enemy_next_base(oracle)
                                    if self.oracle_next_loction is not None:
                                        # await self.do(oracle.move(self.oracle_next_loction))
                                        await self.oracle_move_with_dodge(oracle, self.oracle_next_loction)
                        else:
                            if self.oracle_next_loction == None or oracle.distance_to(self.oracle_next_loction) < 5:
                                self.oracle_next_loction = self.oracle_get_enemy_next_base(oracle)
                            if self.oracle_next_loction is not None:
                                # await self.do(oracle.move(self.oracle_next_loction))
                                await self.oracle_move_with_dodge(oracle, self.oracle_next_loction)
                    else:
                        if AbilityId.BEHAVIOR_PULSARBEAMOFF in await self.get_available_abilities(oracle):
                            if self.known_enemy_units.closer_than(20, oracle).exists:
                                if self.target_of_oracle is None:
                                    self.target_of_oracle = self.oracle_select_enemy_worker_as_target(self.known_enemy_units.closer_than(4, oracle).of_type({UnitTypeId.DRONE}))
                                if self.target_of_oracle is None:
                                    if self.oracle_next_loction == None or oracle.distance_to(self.oracle_next_loction) < 5:
                                        self.oracle_next_loction = self.oracle_get_enemy_next_base(oracle)
                                    if self.oracle_next_loction is not None:
                                        # await self.do(oracle.move(self.oracle_next_loction))
                                        await self.oracle_move_with_dodge(oracle, self.oracle_next_loction)
                                else:
                                    await self.oracle_attck_target(oracle, self.target_of_oracle)
                            else:
                                await self.do(oracle(AbilityId.BEHAVIOR_PULSARBEAMOFF))
                        else:
                            if self.known_enemy_units.closer_than(15, oracle).of_type(self.can_attack_oracle_units).exists:
                                await self.oracle_flee(oracle)
                            else:
                                await self.do(oracle.hold_position())
            else:
                if AbilityId.BEHAVIOR_PULSARBEAMOFF in await self.get_available_abilities(oracle):
                    if self.target_of_oracle is None:
                        self.target_of_oracle = self.oracle_select_enemy_worker_as_target(
                            self.known_enemy_units.closer_than(16, oracle).of_type({UnitTypeId.DRONE}))
                    if self.target_of_oracle is None:
                        if self.oracle_next_loction == None or oracle.distance_to(self.oracle_next_loction) < 5:
                            self.oracle_next_loction = self.oracle_get_enemy_next_base(oracle)
                        if self.oracle_next_loction is not None:
                            # await self.do(oracle.move(self.oracle_next_loction))
                            await self.oracle_move_with_dodge(oracle, self.oracle_next_loction)
                    else:
                        await self.oracle_attck_target(oracle, self.target_of_oracle)
                else:
                    if self.known_enemy_units.closer_than(15, oracle).of_type(self.can_attack_oracle_units).exists:
                        await self.oracle_flee(oracle)
                    else:
                        await self.do(oracle.hold_position())

    async def oracle_move_with_dodge(self, oracle:Unit, dest:Union[Point2, Unit], bias: Union[int, float] = 6):
        can_attack_oracle =  self.known_enemy_units.closer_than(15, oracle).filter(lambda u: u.can_attack_air)

        if len(can_attack_oracle) > 0:

            re_vectors = []
            for enemy in can_attack_oracle:
                if oracle.distance_to(enemy) <= enemy.air_range + 4:
                    this_vector = oracle.position - enemy.position
                    this_vector = this_vector / abs(this_vector)
                    re_vectors.append(this_vector)

            if len(re_vectors) > 0:
                combined_re_vector = Point2((0,0))
                for vector in re_vectors:
                    combined_re_vector += vector

                combined_re_vector = combined_re_vector / abs(combined_re_vector)

                destination = Point2((0,0))
                if isinstance(dest, Unit): destination = dest.position
                elif isinstance(dest, Point2):destination = dest
                forward_vector = destination - oracle.position
                forward_vector = forward_vector / abs(forward_vector)

                combined_vector = combined_re_vector + forward_vector

                if combined_vector.is_same_as(Point2((0,0)), dist = 0.01):
                    if forward_vector.x < 0.02:
                        combined_vector = Point2((1, 0))
                    else:
                        combined_vector = Point2((1, -(forward_vector.y / forward_vector.x)))

                combined_vector = combined_vector / abs(combined_vector)

                mid_point = oracle.position + combined_vector * bias
                await self.do(oracle.move(mid_point))
            else:
                if isinstance(dest, Point2): await self.do(oracle.move(dest))
                elif isinstance(dest, Unit): await self.do(oracle.move(dest.position))
        else:
            if isinstance(dest, Point2): await self.do(oracle.move(dest))
            elif isinstance(dest, Unit): await self.do(oracle.move(dest.position))


    async def investigate_oracle(self):
        if self.units(UnitTypeId.ORACLE).ready.exists:
            investigate_locations = self.state.mineral_field.further_than(15, self.enemy_townhall_locations[-1]).closer_than(35,self.enemy_townhall_locations[-1])
            invest_location = None
            for location in investigate_locations:
                if location.position not in self.enemy_townhall_locations:
                    invest_location = location.position

            if self.scout_oracle.distance_to(invest_location) > 10:
                await self.oracle_move_with_dodge(self.scout_oracle, invest_location)
            else:
                if self.known_enemy_structures.of_type({UnitTypeId.HATCHERY, UnitTypeId.LAIR}).closer_than(10, self.scout_oracle).exists:
                    self.enemy_townhall_locations.append(invest_location)

    async def attack_oracle(self):
        for oracle in self.units(UnitTypeId.ORACLE).ready.filter(lambda u: u.health < 15):
            if self.gather_in_home and oracle.distance_to(self.gather_point) > 8:
                await self.oracle_move_with_dodge(oracle, self.gather_point)


    async def attack_stalker(self):
        pass

    async def train_voidray(self):
        pass


    async def build_roboticsfacility(self):
        if self.townhalls.ready.amount == 2:
            townhall = self.townhalls.furthest_to(self.start_location)
            if self.units(UnitTypeId.ROBOTICSFACILITY).amount < 2:
                pylon = self.units(UnitTypeId.PYLON).closer_than(10, townhall).ready
                if pylon.exists and self.can_afford(UnitTypeId.PYLON):
                    await self.build(UnitTypeId.ROBOTICSFACILITY, near = pylon.random)


    async def build_forge(self):
        if self.units(UnitTypeId.STALKER).exists:
            if not self.units(UnitTypeId.FORGE).ready.exists and self.already_pending(UnitTypeId.FORGE) < 1 and self.can_afford(UnitTypeId.FORGE):
                pylon = self.units(UnitTypeId.PYLON).closer_than(16, self.start_location).ready.random
                await self.build(UnitTypeId.FORGE, near = pylon)

        if not self.units(UnitTypeId.FORGE).ready.exists and self.already_pending(UnitTypeId.FORGE) == 1 and self.can_afford(UnitTypeId.FORGE):
            pylon = self.units(UnitTypeId.PYLON).closer_than(16, self.start_location).ready.random
            await self.build(UnitTypeId.FORGE, near = pylon)

        if self.units(UnitTypeId.FORGE).ready.amount == 1 and not self.already_pending(UnitTypeId.FORGE) and self.can_afford(UnitTypeId.FORGE):
            pylon = self.units(UnitTypeId.PYLON).closer_than(16, self.start_location).ready.random
            await self.build(UnitTypeId.FORGE, near = pylon)


    async def build_twilightcouncil(self):
        if self.units(UnitTypeId.STALKER).ready.exists:
            if not self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.exists and not self.already_pending(UnitTypeId.TWILIGHTCOUNCIL):
                if self.can_afford(UnitTypeId.TWILIGHTCOUNCIL):
                    pylon = self.units(UnitTypeId.PYLON).closer_than(16, self.start_location).ready.random
                    await self.build(UnitTypeId.TWILIGHTCOUNCIL, near = pylon)


    async def train_immortal(self):
        if self.units(UnitTypeId.ROBOTICSFACILITY).ready.exists:
            if self.units(UnitTypeId.IMMORTAL).amount < 3:
                for rob in self.units(UnitTypeId.ROBOTICSFACILITY).ready:
                    if rob.is_idle and self.can_afford(UnitTypeId.IMMORTAL):
                        await self.do(rob.train(UnitTypeId.IMMORTAL))
                        break


    async def train_ob(self):
        if self.units(UnitTypeId.OBSERVER).amount < 2 and self.already_pending(UnitTypeId.OBSERVER) == 0:
            if self.units(UnitTypeId.ROBOTICSFACILITY).ready.exists:
                vr = self.units(UnitTypeId.ROBOTICSFACILITY).ready.first
                if vr.is_idle and self.can_afford(UnitTypeId.OBSERVER):
                    await self.do(vr.train(UnitTypeId.OBSERVER))

    async def defensive(self):
        if self.defend_home:
            for force in self.units.of_type({UnitTypeId.ZEALOT, UnitTypeId.STALKER, UnitTypeId.ADEPT}).ready:
                enemy_nearby = set()
                for townhall in self.townhalls:
                    enemy_near_townhall = set(self.known_enemy_units.closer_than(16, townhall))
                    enemy_nearby = enemy_nearby.union(enemy_near_townhall)
                if len(enemy_nearby) != 0:
                    await self.do(force.attack(random.choice(list(enemy_nearby))))


    async def all_attack(self):
        if self.all_force_attack and not self.gather_in_home:
            await self.leader_attack()
            await self.zealot_attack()
            await self.adept_attack()
            await self.stalker_attack()
            await self.immortal_attack()

    async def leader_attack(self):
        if self.attack_leader is not None:
            closest_enemy = self.known_enemy_units.closest_to(self.attack_leader)
            if closest_enemy.distance_to(self.attack_leader) < 12:
                await self.do(self.attack_leader.attack(closest_enemy))
            else:
                if self.units.of_type({UnitTypeId.ZEALOT, UnitTypeId.ADEPT, UnitTypeId.STALKER}).closer_than(9, self.attack_leader).ready.amount < 6 and \
                    not self.attack_leader.is_attacking:
                    await self.do(self.attack_leader.hold_position())
                elif self.units.of_type({UnitTypeId.ZEALOT, UnitTypeId.ADEPT, UnitTypeId.STALKER}).closer_than(9, self.attack_leader).ready.amount >= 6:
                    target = self.known_enemy_structures.of_type({UnitTypeId.LAIR, UnitTypeId.HATCHERY, UnitTypeId.HIVE}).closest_to(self.attack_leader)
                    await self.do(self.attack_leader.move(target.position.to2))
                    # await self.do(self.attack_leader.move(self.enemy_start_locations[0]))

    async def zealot_attack(self):
        for zealot in self.units(UnitTypeId.ZEALOT).ready:
            if not zealot.is_attacking:
                enemy_near_the_force = self.known_enemy_units.closer_than(8, zealot)
                if enemy_near_the_force.exists:
                    if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                        await self.do(zealot.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))
                    else:
                        await self.do(zealot.attack(enemy_near_the_force.random))
                else:
                    if self.attack_leader is not None and zealot != self.attack_leader:
                        await self.do(zealot.move(self.attack_leader.position))
            elif zealot.is_attacking:
                if zealot.order_target is not None and isinstance(zealot.order_target, int):
                    if zealot.order_target not in {UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.RAVAGER, UnitTypeId.HYDRALISK, UnitTypeId.QUEEN}:
                        enemy_near_the_force = self.known_enemy_units.closer_than(8, zealot)
                        if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                            await self.do(zealot.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))

    async def stalker_attack(self):
        for stalker in self.units(UnitTypeId.STALKER).ready:
            if not stalker.is_attacking:
                enemy_near_the_force = self.known_enemy_units.closer_than(8, stalker)
                if enemy_near_the_force.exists:
                    if enemy_near_the_force.filter(lambda u: u.is_flying).exists:
                        await self.do(stalker.attack(enemy_near_the_force.filter(lambda u: u.is_flying).random))
                    elif enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                        await self.do(stalker.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))
                    else:
                        await self.do(stalker.attack(enemy_near_the_force.random))
                else:
                    if self.attack_leader is not None and stalker != self.attack_leader: await self.do(stalker.move(self.attack_leader.position))
            elif stalker.is_attacking:
                if stalker.order_target is not None and isinstance(stalker.order_target, int):
                    if stalker.order_target not in {UnitTypeId.MUTALISK, UnitTypeId.CORRUPTOR, UnitTypeId.OVERSEER}:
                        enemy_near_the_force = self.known_enemy_units.closer_than(8, stalker)
                        if enemy_near_the_force.filter(lambda u: u.is_flying).exists:
                            await self.do(stalker.attack(enemy_near_the_force.filter(lambda u: u.is_flying).random))
                    elif stalker.order_target not in {UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.RAVAGER, UnitTypeId.HYDRALISK, UnitTypeId.QUEEN}:
                        enemy_near_the_force = self.known_enemy_units.closer_than(8, stalker)
                        if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                            await self.do(stalker.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))

    async def adept_attack(self):
        for adept in self.units(UnitTypeId.ADEPT).ready:
            if not adept.is_attacking:
                enemy_near_the_force = self.known_enemy_units.closer_than(8, adept)
                if enemy_near_the_force.exists:
                    if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                        await self.do(adept.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))
                    else:
                        await self.do(adept.attack(enemy_near_the_force.random))
                else:
                    if self.attack_leader is not None and adept != self.attack_leader: await self.do(adept.move(self.attack_leader.position))
            elif adept.is_attacking:
                if adept.order_target is not None and isinstance(adept.order_target, int):
                    if adept.order_target not in {UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.RAVAGER, UnitTypeId.HYDRALISK, UnitTypeId.QUEEN}:
                        enemy_near_the_force = self.known_enemy_units.closer_than(8, adept)
                        if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                            await self.do(adept.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))

    async def immortal_attack(self):
        for immortal in self.units(UnitTypeId.IMMORTAL).ready:
            if not immortal.is_attacking:
                enemy_near_the_force = self.known_enemy_units.closer_than(8, immortal)
                if enemy_near_the_force.exists:
                    if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                        await self.do(immortal.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))
                    else:
                        await self.do(immortal.attack(enemy_near_the_force.random))
                else:
                    if self.attack_leader is not None and immortal != self.attack_leader: await self.do(immortal.move(self.attack_leader.position))
            elif immortal.is_attacking:
                if immortal.order_target is not None and isinstance(immortal.order_target, int):
                    if immortal.order_target not in {UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.RAVAGER, UnitTypeId.HYDRALISK, UnitTypeId.QUEEN}:
                        enemy_near_the_force = self.known_enemy_units.closer_than(8, immortal)
                        if enemy_near_the_force.filter(lambda u: u.is_biological).exists:
                            await self.do(immortal.attack(enemy_near_the_force.filter(lambda u: u.is_biological).random))

    async def expand(self):
        if self.townhalls.amount < 2 and self.minerals >= 500 and self.units(UnitTypeId.WARPGATE).ready.exists:
            await self.expand_now()

        if self.townhalls.amount < 3 and self.units(UnitTypeId.ROBOTICSFACILITY).ready.exists and self.minerals >= 500:
            await self.expand_now()

        if self.townhalls.amount >= 3 and not self.already_pending(UnitTypeId.NEXUS) and self.have_resource_exhausted:

            have_emepty_townhall = False
            for townhall in self.townhalls.ready:
                worker_near = self.workers.closer_than(10, townhall).amount
                worker_need = townhall.ideal_harvesters
                for geyser in self.geysers.closer_than(6, townhall):
                    worker_need += geyser.ideal_harvesters
                if worker_near + 3 < worker_need:
                    have_emepty_townhall = True
                    break

            if not have_emepty_townhall and self.minerals >= 500:
                await self.expand_now()

    async def upgrade_charge(self):
        if self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.exists:
            vt = self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.first
            if self.can_afford(UpgradeId.CHARGE) and AbilityId.RESEARCH_CHARGE in await self.get_available_abilities(vt) :
                await self.do(vt.research(UpgradeId.CHARGE))

    async def upgrade_blink(self):
        if self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.exists:
            vt = self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.first
            if self.can_afford(UpgradeId.BLINKTECH) and \
                    AbilityId.RESEARCH_BLINK in await self.get_available_abilities(vt) and \
                    self.units(UnitTypeId.STALKER).amount >= 5:
                await self.do(vt.research(UpgradeId.BLINKTECH))

    async def upgrade_resonating_glaives(self):
        if self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.exists:
            vt = self.units(UnitTypeId.TWILIGHTCOUNCIL).ready.first
            if self.minerals > 100 and \
                    self.vespene > 100 and \
                    AbilityId.RESEARCH_ADEPTRESONATINGGLAIVES in await self.get_available_abilities(vt):
                await self.do(vt(AbilityId.RESEARCH_ADEPTRESONATINGGLAIVES))

    async def upgrade_forge(self):
        if self.units.of_type({UnitTypeId.ZEALOT, UnitTypeId.STALKER, UnitTypeId.ADEPT}).amount > 12:
            if self.units(UnitTypeId.FORGE).ready.exists:
                for forge in self.units(UnitTypeId.FORGE).ready:
                    if forge.is_idle:

                        if AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL1 in await self.get_available_abilities(
                                forge) and \
                                self.can_afford(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1):
                            await self.do(forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1))

                        if AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL2 in await self.get_available_abilities(
                                forge) and \
                                self.can_afford(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL2):
                            await self.do(forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL2))

                        if AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL3 in await self.get_available_abilities(
                                forge) and \
                                self.can_afford(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL3):
                            await self.do(forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL3))

                        if AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL1 in await self.get_available_abilities(forge) and\
                                self.can_afford(UpgradeId.PROTOSSGROUNDARMORSLEVEL1):
                            await self.do(forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL1))

                        if AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2 in await self.get_available_abilities(forge) and\
                                self.can_afford(UpgradeId.PROTOSSGROUNDARMORSLEVEL2):
                            await self.do(forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL2))

                        if AbilityId.FORGERESEARCH_PROTclOSSGROUNDARMORLEVEL3 in await self.get_available_abilities(
                                forge) and \
                                self.can_afford(UpgradeId.PROTOSSAIRARMORSLEVEL3):
                            await self.do(forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL3))

                        if AbilityId.FORGERESEARCH_PROTOSSSHIELDSLEVEL1 in await self.get_available_abilities(forge) and\
                                self.can_afford(UpgradeId.PROTOSSSHIELDSLEVEL1):
                            await self.do(forge.research(UpgradeId.PROTOSSSHIELDSLEVEL1))

                        if AbilityId.FORGERESEARCH_PROTOSSSHIELDSLEVEL2 in await self.get_available_abilities(forge) and\
                                self.can_afford(UpgradeId.PROTOSSSHIELDSLEVEL2):
                            await self.do(forge.research(UpgradeId.PROTOSSSHIELDSLEVEL2))

                        if AbilityId.FORGERESEARCH_PROTOSSSHIELDSLEVEL3 in await self.get_available_abilities(forge) and\
                                self.can_afford(UpgradeId.PROTOSSSHIELDSLEVEL3):
                            await self.do(forge.research(UpgradeId.PROTOSSSHIELDSLEVEL3))

    async def observer_investigate(self):
        pass

    async def train_force(self):
        await self.train_immortal()
        await self.train_force_in_gate()
        # await self.train_ob()
        




def main():
    run_game(
        maps.get("AcropolisLE"),
        [Bot(Race.Protoss, OracleBot()), Computer(Race.Zerg, Difficulty.Easy)],
        realtime = True
    )

if __name__ == "__main__":
    main()
